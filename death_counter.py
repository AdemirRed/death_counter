"""
Death Counter - Backend
Rode com: python death_counter.py  OU  death_counter.exe (como Administrador)
Instale:  python -m pip install flask flask-cors mss pillow numpy opencv-python pytesseract keyboard
"""
import sys, io, os, time, json, threading, logging, webbrowser, socket
from pathlib import Path
from datetime import datetime

# ── pasta base: funciona tanto como .py quanto como .exe (PyInstaller) ──
# Quando empacotado pelo PyInstaller, sys.frozen=True e os HTMLs ficam em
# sys._MEIPASS (pasta temporaria). Config e templates ficam sempre ao lado do .exe.
def _get_base():
    if getattr(sys, "frozen", False):
        # rodando como .exe — HTMLs estão em _MEIPASS, config/templates ao lado do .exe
        return Path(sys.executable).parent.resolve()
    return Path(__file__).parent.resolve()

def _get_static():
    """Pasta onde estão os arquivos HTML (dentro do bundle no .exe)."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS).resolve()
    return Path(__file__).parent.resolve()

BASE_DIR      = _get_base()
STATIC_DIR    = _get_static()
CONFIG_FILE   = BASE_DIR / "config.json"
TEMPLATES_DIR = BASE_DIR / "templates"
TEMPLATES_DIR.mkdir(exist_ok=True)

# ── imports opcionais (sem crashes) ────────────────────────────────
MSS_OK = False
PIL_OK = False
CV2_OK = False
TESS_OK = False
KB_OK   = False

try:
    import mss as mss_lib
    MSS_OK = True
except ImportError:
    print("[AVISO] mss nao instalado  →  python -m pip install mss")

try:
    from PIL import Image as PILImage
    import numpy as np
    PIL_OK = True
except ImportError:
    print("[AVISO] pillow/numpy nao instalados  →  python -m pip install pillow numpy")

try:
    import cv2
    CV2_OK = True
except ImportError:
    print("[AVISO] opencv nao instalado  →  python -m pip install opencv-python")

try:
    import pytesseract
    TESS_OK = True
except ImportError:
    print("[AVISO] pytesseract nao instalado  →  python -m pip install pytesseract")

try:
    import keyboard as kb
    KB_OK = True
except ImportError:
    print("[AVISO] keyboard nao instalado  →  python -m pip install keyboard")

TRAY_OK = False
try:
    import pystray as _pystray
    from PIL import Image as _TrayImage, ImageDraw as _TrayDraw
    TRAY_OK = True
except ImportError:
    pass

SOUND_OK = False
try:
    import winsound as _winsound
    SOUND_OK = True
except ImportError:
    pass

def _beep_async(freq: int, ms: int):
    if not SOUND_OK:
        return
    freq = max(37, min(32767, freq))
    threading.Thread(target=lambda: _winsound.Beep(freq, ms), daemon=True).start()

try:
    from flask import Flask, jsonify, request, send_from_directory, Response
    from flask_cors import CORS
except ImportError:
    sys.exit("[ERRO FATAL] Flask nao encontrado  →  python -m pip install flask flask-cors")

# ── logging ────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(BASE_DIR / "death_counter.log", encoding="utf-8"),
    ]
)
log = logging.getLogger("DC")

# ── config ─────────────────────────────────────────────────────────
DEFAULT_CONFIG = {
    "port": 8765,
    "game_name": "Meu Jogo",
    "detection_mode": "none",
    "ocr_keywords": ["YOU DIED", "GAME OVER", "DEATH", "WASTED", "VOCE MORREU"],
    "ocr_region": None,
    "template_threshold": 0.80,
    "detection_interval": 1.0,
    "cooldown_after_death": 4.0,
    "tesseract_path": "",
    "overlay_style": "dark",
    "counter_label": "MORTES",
    "show_session_time": True,
    "hotkey_add":      "f1",
    "hotkey_remove":   "f2",
    "hotkey_reset":    "",
    "hotkey_capture":  "",
    "hotkeys_enabled": True,
}

def load_cfg():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            c = json.load(f)
        for k, v in DEFAULT_CONFIG.items():
            c.setdefault(k, v)
        return c
    return DEFAULT_CONFIG.copy()

def save_cfg(c):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(c, f, indent=2, ensure_ascii=False)

config = load_cfg()

# ── estado ─────────────────────────────────────────────────────────
lock = threading.Lock()
state = {
    "deaths": 0,
    "session_start": datetime.now().isoformat(),
    "last_detection": None,
    "detection_active": False,
    "detection_status": "parado",
    "last_error": "",
    "hotkeys_registered": False,
}

# ── captura de tela ─────────────────────────────────────────────────
def capture_screen(region=None):
    """Retorna PIL Image da tela (ou região). None se libs faltando."""
    if not MSS_OK or not PIL_OK:
        return None
    with mss_lib.MSS() as sct:
        if region and len(region) == 4:
            mon = {"left": region[0], "top": region[1],
                   "width": region[2], "height": region[3]}
        else:
            mon = sct.monitors[1]
        shot = sct.grab(mon)
        return PILImage.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")

def screen_png_bytes():
    img = capture_screen()
    if img is None:
        return None
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()

# ── detecção ────────────────────────────────────────────────────────
def detect_template(img):
    if not CV2_OK:
        return False, "opencv nao instalado"
    if not PIL_OK:
        return False, "pillow nao instalado"

    templates = (
        list(TEMPLATES_DIR.glob("*.png")) +
        list(TEMPLATES_DIR.glob("*.jpg")) +
        list(TEMPLATES_DIR.glob("*.jpeg"))
    )
    if not templates:
        return False, "Nenhum template na pasta /templates/"

    screen_bgr   = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    screen_gray  = cv2.cvtColor(screen_bgr, cv2.COLOR_BGR2GRAY)
    screen_eq    = cv2.equalizeHist(screen_gray)
    screen_edges = cv2.Canny(screen_gray, 50, 150)
    sh, sw       = screen_gray.shape[:2]
    thresh       = float(config.get("template_threshold", 0.80))

    # Apenas TM_CCOEFF_NORMED: coeficiente de correlação normalizado real (-1 a 1).
    # TM_CCORR_NORMED foi removido pois retorna valores inflados (~0.9+) mesmo sem
    # correspondência real, causando muitos falsos positivos.
    scales = [1.0, 0.9, 0.8, 1.1, 1.2]

    best_val  = 0.0
    best_name = ""

    for tp_path in templates:
        tpl_orig = cv2.imread(str(tp_path), cv2.IMREAD_GRAYSCALE)
        if tpl_orig is None:
            log.warning(f"Nao foi possivel ler template: {tp_path.name}")
            continue

        for scale in scales:
            nh = int(tpl_orig.shape[0] * scale)
            nw = int(tpl_orig.shape[1] * scale)
            if nh < 8 or nw < 8 or nh > sh or nw > sw:
                continue

            tpl       = cv2.resize(tpl_orig, (nw, nh), interpolation=cv2.INTER_AREA)
            tpl_eq    = cv2.equalizeHist(tpl)
            tpl_edges = cv2.Canny(tpl, 50, 150)

            scores = []
            # Cinza puro — TM_CCOEFF_NORMED
            r = cv2.matchTemplate(screen_gray, tpl, cv2.TM_CCOEFF_NORMED)
            _, mv, _, _ = cv2.minMaxLoc(r)
            scores.append(mv)

            # Histograma equalizado — robusto a brilho/contraste diferentes
            r2 = cv2.matchTemplate(screen_eq, tpl_eq, cv2.TM_CCOEFF_NORMED)
            _, mv2, _, _ = cv2.minMaxLoc(r2)
            scores.append(mv2)

            # Bordas Canny — robusto a mudanças de cor, ótimo para logos/texto
            if tpl_edges.shape[0] <= sh and tpl_edges.shape[1] <= sw:
                r3 = cv2.matchTemplate(screen_edges, tpl_edges, cv2.TM_CCOEFF_NORMED)
                _, mv3, _, _ = cv2.minMaxLoc(r3)
                scores.append(mv3)

            val = max(scores)
            if val > best_val:
                best_val  = val
                best_name = f"{tp_path.name} @{scale:.2f}x"

    if best_val >= thresh:
        return True, f"Template '{best_name}' conf={best_val:.2f}"
    return False, f"Melhor conf={best_val:.2f} (minimo={thresh}) — {best_name or 'nenhum'}"


def detect_ocr(img):
    if not TESS_OK:
        return False, "pytesseract nao instalado"
    tp = config.get("tesseract_path", "")
    if tp:
        pytesseract.pytesseract.tesseract_cmd = tp

    # pré-processamento: escala 2x + threshold para melhorar OCR
    if PIL_OK:
        w, h = img.size
        img_proc = img.resize((w * 2, h * 2), PILImage.LANCZOS).convert("L")
        if CV2_OK:
            arr = np.array(img_proc)
            _, arr = cv2.threshold(arr, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            img_proc = PILImage.fromarray(arr)
    else:
        img_proc = img

    text = pytesseract.image_to_string(img_proc, config="--psm 3").upper()
    for kw in config.get("ocr_keywords", []):
        if kw.upper() in text:
            return True, f"OCR encontrou: '{kw}'"
    return False, "OCR: nenhuma palavra-chave encontrada"

# ── mortes ──────────────────────────────────────────────────────────
def add_death(source="manual"):
    with lock:
        state["deaths"] += 1
        state["last_detection"] = datetime.now().isoformat()
        state["detection_status"] = "detectado"
        d = state["deaths"]
    log.info(f"+1 morte [{source}] total={d}")
    def _snd_add():
        _beep_async(880, 80); time.sleep(0.11); _beep_async(660, 120)
    threading.Thread(target=_snd_add, daemon=True).start()

    def _back():
        time.sleep(2)
        with lock:
            if state["detection_status"] == "detectado":
                state["detection_status"] = "rodando" if state["detection_active"] else "parado"
    threading.Thread(target=_back, daemon=True).start()

def remove_death():
    with lock:
        state["deaths"] = max(0, state["deaths"] - 1)
        d = state["deaths"]
    log.info(f"-1 morte total={d}")
    _beep_async(440, 120)

def reset_deaths():
    with lock:
        state["deaths"] = 0
        state["session_start"] = datetime.now().isoformat()
        state["last_detection"] = None
    log.info("Reset!")
    def _snd_reset():
        _beep_async(330, 80); time.sleep(0.10)
        _beep_async(440, 80); time.sleep(0.10)
        _beep_async(550, 120)
    threading.Thread(target=_snd_reset, daemon=True).start()

# ── screenshot pendente (capturado por hotkey, aguardando seleção de região) ──
_pending_screenshot = None  # bytes ou None

def capture_and_store_pending():
    global _pending_screenshot
    img = capture_screen()
    if img is None:
        log.warning("Captura pendente falhou — mss/pillow instalados?")
        return
    buf = io.BytesIO()
    img.save(buf, "PNG")
    _pending_screenshot = buf.getvalue()
    log.info("Screenshot pendente capturado para seleção de template")

# ── loop de detecção ────────────────────────────────────────────────
_det_thread = None
_det_stop   = threading.Event()
_cooldown   = False

def _det_loop():
    global _cooldown
    log.info("Loop de deteccao iniciado.")
    with lock:
        state["detection_active"] = True
        state["detection_status"] = "rodando"

    while not _det_stop.is_set():
        try:
            if _cooldown:
                time.sleep(0.4)
                continue

            mode = config.get("detection_mode", "none")
            if mode == "none":
                time.sleep(1)
                continue

            img = capture_screen(config.get("ocr_region"))
            if img is None:
                with lock:
                    state["last_error"] = "Captura falhou (mss/pillow instalados?)"
                time.sleep(1)
                continue

            hit, msg = False, ""
            if mode == "ocr":
                hit, msg = detect_ocr(img)
            elif mode == "template":
                hit, msg = detect_template(img)

            with lock:
                state["last_error"] = "" if hit else msg

            if hit:
                add_death(source=mode)
                _cooldown = True
                def _end_cd():
                    global _cooldown
                    time.sleep(config.get("cooldown_after_death", 4.0))
                    _cooldown = False
                threading.Thread(target=_end_cd, daemon=True).start()

        except Exception as e:
            log.error(f"Erro no loop: {e}")
            with lock:
                state["last_error"] = str(e)

        time.sleep(config.get("detection_interval", 1.0))

    with lock:
        state["detection_active"] = False
        state["detection_status"] = "parado"
    log.info("Loop de deteccao encerrado.")

def start_det():
    global _det_thread, _det_stop
    if _det_thread and _det_thread.is_alive():
        return False, "já rodando"
    _det_stop.clear()
    _det_thread = threading.Thread(target=_det_loop, daemon=True)
    _det_thread.start()
    def _snd_start():
        _beep_async(660, 80); time.sleep(0.11); _beep_async(880, 80)
    threading.Thread(target=_snd_start, daemon=True).start()
    return True, "iniciado"

def stop_det():
    _det_stop.set()
    def _snd_stop():
        _beep_async(440, 80); time.sleep(0.11); _beep_async(330, 120)
    threading.Thread(target=_snd_stop, daemon=True).start()

# ── hotkeys ─────────────────────────────────────────────────────────
_hk_hooks = []

def register_hotkeys():
    global _hk_hooks
    if not KB_OK:
        log.warning("keyboard nao instalado — hotkeys desativadas")
        with lock:
            state["hotkeys_registered"] = False
        return

    for h in _hk_hooks:
        try: kb.remove_hotkey(h)
        except: pass
    _hk_hooks.clear()

    if not config.get("hotkeys_enabled", True):
        with lock:
            state["hotkeys_registered"] = False
        return

    registered = 0
    for cfg_key, fn in [
        ("hotkey_add",     lambda: add_death("hotkey")),
        ("hotkey_remove",  remove_death),
        ("hotkey_reset",   reset_deaths),
        ("hotkey_capture", lambda: threading.Thread(target=capture_and_store_pending, daemon=True).start()),
    ]:
        k = str(config.get(cfg_key, "")).strip()
        if not k or k == "—":
            continue
        try:
            h = kb.add_hotkey(k, fn)
            _hk_hooks.append(h)
            log.info(f"Hotkey registrada: '{k}' → {cfg_key}")
            registered += 1
        except Exception as e:
            log.error(f"Falha ao registrar hotkey '{k}': {e}")

    with lock:
        state["hotkeys_registered"] = registered > 0
    log.info(f"{registered} hotkey(s) registrada(s).")

# ── Flask app ───────────────────────────────────────────────────────
app = Flask(__name__, static_folder=str(STATIC_DIR))
CORS(app)

# garante CORS em todas as respostas (inclusive erros)
@app.after_request
def add_cors(r):
    r.headers["Access-Control-Allow-Origin"]  = "*"
    r.headers["Access-Control-Allow-Methods"] = "GET,POST,DELETE,OPTIONS"
    r.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return r

@app.route("/favicon.ico")
def favicon():
    svg = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><text y="14" font-size="14">\xf0\x9f\x92\x80</text></svg>'
    return Response(svg, mimetype="image/svg+xml")

# preflight OPTIONS global
@app.route("/<path:p>", methods=["OPTIONS"])
def options_handler(p):
    return "", 204

# ── /state ──────────────────────────────────────────────────────────
@app.route("/state")
def r_state():
    with lock:
        s = dict(state)
    return jsonify({
        **s,
        "has_pending_screenshot": _pending_screenshot is not None,
        "config": config,
        "libs": {
            "mss":      MSS_OK,
            "pillow":   PIL_OK,
            "cv2":      CV2_OK,
            "tess":     TESS_OK,
            "keyboard": KB_OK,
        }
    })

# ── mortes ──────────────────────────────────────────────────────────
@app.route("/deaths/increment", methods=["POST"])
def r_inc():
    add_death("manual")
    with lock:
        return jsonify({"ok": True, "deaths": state["deaths"]})

@app.route("/deaths/decrement", methods=["POST"])
def r_dec():
    remove_death()
    with lock:
        return jsonify({"ok": True, "deaths": state["deaths"]})

@app.route("/deaths/reset", methods=["POST"])
def r_reset():
    reset_deaths()
    return jsonify({"ok": True, "deaths": 0})

@app.route("/deaths/set", methods=["POST"])
def r_set():
    data = request.get_json(silent=True) or {}
    v = max(0, int(data.get("value", 0)))
    with lock:
        state["deaths"] = v
    log.info(f"Definido: {v}")
    return jsonify({"ok": True, "deaths": v})

# ── detecção ────────────────────────────────────────────────────────
@app.route("/detection/start", methods=["POST"])
def r_start():
    ok, msg = start_det()
    return jsonify({"ok": True, "started": ok, "msg": msg})

@app.route("/detection/stop", methods=["POST"])
def r_stop():
    stop_det()
    return jsonify({"ok": True})

# ── config ──────────────────────────────────────────────────────────
@app.route("/config", methods=["GET"])
def r_cfg_get():
    return jsonify(config)

@app.route("/config", methods=["POST"])
def r_cfg_set():
    global config
    data = request.get_json(silent=True) or {}
    config.update(data)
    save_cfg(config)
    register_hotkeys()
    return jsonify({"ok": True})

# ── templates: listar ───────────────────────────────────────────────
@app.route("/templates", methods=["GET"])
def r_tpls():
    exts = {".png", ".jpg", ".jpeg"}
    files = sorted(f.name for f in TEMPLATES_DIR.iterdir()
                   if f.suffix.lower() in exts)
    return jsonify({"templates": files})

# ── templates: upload ───────────────────────────────────────────────
@app.route("/templates/upload", methods=["POST"])
def r_tpl_upload():
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "campo 'file' ausente"}), 400
    f    = request.files["file"]
    name = Path(f.filename).name
    ext  = Path(name).suffix.lower()
    if ext not in {".png", ".jpg", ".jpeg"}:
        return jsonify({"ok": False, "error": "apenas PNG/JPG aceitos"}), 400
    dest = TEMPLATES_DIR / name
    f.save(str(dest))
    log.info(f"Template salvo: {name} ({dest.stat().st_size} bytes)")
    return jsonify({"ok": True, "saved": name})

# ── templates: captura de tela → template ───────────────────────────
@app.route("/templates/screenshot", methods=["POST"])
def r_tpl_screenshot():
    if not MSS_OK or not PIL_OK:
        return jsonify({"ok": False, "error": "pip install mss pillow"}), 500
    region = (request.get_json(silent=True) or {}).get("region")
    img = capture_screen(region)
    if img is None:
        return jsonify({"ok": False, "error": "captura falhou"}), 500
    name = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    img.save(str(TEMPLATES_DIR / name))
    log.info(f"Screenshot salvo: {name}")
    return jsonify({"ok": True, "saved": name})

# ── tela atual → preview ─────────────────────────────────────────────
@app.route("/screenshot/preview")
def r_preview():
    if not MSS_OK or not PIL_OK:
        return Response("libs faltando", status=500)
    data = screen_png_bytes()
    if data is None:
        return Response("falha na captura", status=500)
    return Response(data, mimetype="image/png",
                    headers={"Cache-Control": "no-store"})

# ── captura pendente (para seleção de região no browser) ──────────────
@app.route("/screenshot/capture_pending", methods=["POST"])
def r_capture_pending():
    if not MSS_OK or not PIL_OK:
        return jsonify({"ok": False, "error": "pip install mss pillow"}), 500
    threading.Thread(target=capture_and_store_pending, daemon=True).start()
    return jsonify({"ok": True})

@app.route("/screenshot/pending")
def r_pending():
    if _pending_screenshot is None:
        return Response("nenhum", status=404)
    return Response(_pending_screenshot, mimetype="image/png",
                    headers={"Cache-Control": "no-store"})

@app.route("/screenshot/clear_pending", methods=["POST"])
def r_clear_pending():
    global _pending_screenshot
    _pending_screenshot = None
    return jsonify({"ok": True})

# ── templates: deletar ───────────────────────────────────────────────
@app.route("/templates/<name>", methods=["DELETE"])
def r_tpl_del(name):
    p = TEMPLATES_DIR / Path(name).name
    if p.exists():
        p.unlink()
        log.info(f"Template removido: {name}")
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "nao encontrado"}), 404

# ── hotkeys: recarregar ──────────────────────────────────────────────
@app.route("/hotkeys/reload", methods=["POST"])
def r_hk_reload():
    register_hotkeys()
    with lock:
        return jsonify({"ok": True, "registered": state["hotkeys_registered"]})

# ── debug: testa se o servidor está vivo ─────────────────────────────
@app.route("/ping")
def r_ping():
    return jsonify({"ok": True, "pong": True})

# ── info de rede (IP local para celular) ──────────────────────────────
@app.route("/network/info")
def r_network():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
    except Exception:
        ip = "127.0.0.1"
    port = config.get("port", 8765)
    return jsonify({"ip": ip, "port": port, "url": f"http://{ip}:{port}/"})

# ── arquivos estáticos ───────────────────────────────────────────────
@app.route("/")
def r_index():
    return send_from_directory(str(STATIC_DIR), "controller.html")

@app.route("/<path:fn>")
def r_static(fn):
    return send_from_directory(str(STATIC_DIR), fn)

# ── bandeja do sistema (system tray) ─────────────────────────────────
def _criar_icone_tray(size: int = 64):
    img = _TrayImage.new("RGBA", (size, size), (0, 0, 0, 0))
    d = _TrayDraw.Draw(img)
    m = size / 64

    def p(v): return int(round(v * m))

    d.ellipse([p(2), p(2), p(62), p(62)], fill=(130, 0, 0, 255))
    d.ellipse([p(8), p(5), p(56), p(50)], fill=(215, 215, 215, 255))
    d.ellipse([p(14), p(15), p(26), p(28)], fill=(40, 0, 0, 255))
    d.ellipse([p(37), p(15), p(49), p(28)], fill=(40, 0, 0, 255))
    d.polygon([(p(31), p(30)), (p(26), p(38)), (p(36), p(38))], fill=(40, 0, 0, 255))
    d.rectangle([p(13), p(42), p(51), p(60)], fill=(215, 215, 215, 255))
    for x_orig in [20, 28, 36, 44]:
        d.line([(p(x_orig), p(42)), (p(x_orig), p(60))],
               fill=(100, 0, 0, 255), width=max(1, p(1.5)))
    return img


def _run_tray(port: int):
    def on_open(icon, item):
        webbrowser.open(f"http://localhost:{port}/")

    def on_toggle_det(icon, item):
        with lock:
            ativo = state["detection_active"]
        if ativo:
            stop_det()
            log.info("Detecção pausada pelo tray.")
        else:
            start_det()
            log.info("Detecção retomada pelo tray.")

    def on_quit(icon, item):
        icon.stop()
        os._exit(0)

    def det_label(item):
        with lock:
            ativo = state["detection_active"]
        return "Pausar Detecção" if ativo else "Retomar Detecção"

    menu = _pystray.Menu(
        _pystray.MenuItem("Abrir Painel", on_open, default=True),
        _pystray.MenuItem(det_label, on_toggle_det),
        _pystray.Menu.SEPARATOR,
        _pystray.MenuItem("Fechar Death Counter", on_quit),
    )

    icon = _pystray.Icon(
        "death_counter",
        _criar_icone_tray(64),
        f"Death Counter — porta {port}",
        menu,
    )
    icon.run()


# ── main ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = config.get("port", 8765)
    save_cfg(config)
    register_hotkeys()

    log.info("=" * 50)
    log.info("Death Counter iniciando...")
    log.info(f"Painel:   http://localhost:{port}/")
    log.info(f"Overlay:  http://localhost:{port}/obs_overlay.html")
    log.info("=" * 50)

    # Flask roda em thread background
    flask_thread = threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False),
        daemon=True,
        name="flask",
    )
    flask_thread.start()

    # Abre o painel no browser após o servidor subir
    def _open_browser():
        time.sleep(1.5)
        webbrowser.open(f"http://localhost:{port}/")
    threading.Thread(target=_open_browser, daemon=True).start()

    # Ícone na bandeja do Windows (bloqueia até o usuário fechar)
    if TRAY_OK:
        _run_tray(port)
    else:
        log.warning("pystray nao disponivel — instale: pip install pystray")
        log.warning("Mantenha esta janela aberta. Ctrl+C para encerrar.")
        try:
            flask_thread.join()
        except KeyboardInterrupt:
            log.info("Encerrando.")
            sys.exit(0)
