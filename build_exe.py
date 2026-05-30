"""
build_exe.py — Gera o death_counter.exe com PyInstaller
Execute: python build_exe.py
"""
import subprocess, sys, shutil
from pathlib import Path

BASE = Path(__file__).parent.resolve()


def gerar_icone_ico(dest: Path):
    """Desenha ícone de caveira em múltiplas resoluções e salva como .ico."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "pillow"], check=True)
        from PIL import Image, ImageDraw

    sizes = [16, 32, 48, 64, 256]
    images = []

    for s in sizes:
        img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        m = s / 64

        def p(v): return int(round(v * m))

        # Círculo vermelho escuro (fundo)
        d.ellipse([p(2), p(2), p(62), p(62)], fill=(130, 0, 0, 255))
        # Crânio cinza
        d.ellipse([p(8), p(5), p(56), p(50)], fill=(215, 215, 215, 255))
        # Olho esquerdo
        d.ellipse([p(14), p(15), p(26), p(28)], fill=(40, 0, 0, 255))
        # Olho direito
        d.ellipse([p(37), p(15), p(49), p(28)], fill=(40, 0, 0, 255))
        # Nariz (triângulo)
        d.polygon([(p(31), p(30)), (p(26), p(38)), (p(36), p(38))], fill=(40, 0, 0, 255))
        # Mandíbula
        d.rectangle([p(13), p(42), p(51), p(60)], fill=(215, 215, 215, 255))
        # Divisórias dos dentes
        for x_orig in [20, 28, 36, 44]:
            d.line([(p(x_orig), p(42)), (p(x_orig), p(60))],
                   fill=(100, 0, 0, 255), width=max(1, p(1.5)))

        images.append(img)

    images[0].save(str(dest), format="ICO",
                   sizes=[(s, s) for s in sizes],
                   append_images=images[1:])
    print(f"[OK] Ícone gerado: {dest}")


# ── 1. Instalar dependências de build ──────────────────────────────────────
subprocess.run(
    [sys.executable, "-m", "pip", "install", "pyinstaller", "pystray", "pillow"],
    check=True
)

# ── 2. Gerar ícone .ico ────────────────────────────────────────────────────
ico_path = BASE / "death_counter.ico"
gerar_icone_ico(ico_path)

# ── 3. Montar lista de datas (HTMLs + pix.png se existir) ─────────────────
datas = [
    (str(BASE / "controller.html"),  "."),
    (str(BASE / "obs_overlay.html"), "."),
    (str(BASE / "README.md"),        "."),
]

pix_path = BASE / "pix.png"
if pix_path.exists():
    datas.append((str(pix_path), "."))
    print("[OK] pix.png incluído no bundle.")
else:
    print("[INFO] pix.png não encontrada — coloque na pasta antes de rodar este script para incluir o QR code PIX.")

datas_spec = "\n        ".join(f"(r'{p}', '{d}')," for p, d in datas)

# ── 4. Criar .spec ─────────────────────────────────────────────────────────
spec = f"""# -*- mode: python ; coding: utf-8 -*-
a = Analysis(
    [r'{BASE / "death_counter.py"}'],
    pathex=[r'{BASE}'],
    binaries=[],
    datas=[
        {datas_spec}
    ],
    hiddenimports=[
        'flask', 'flask_cors', 'werkzeug', 'jinja2', 'click',
        'mss', 'PIL', 'PIL.Image', 'PIL.ImageDraw', 'numpy', 'cv2',
        'pytesseract', 'keyboard', 'pystray',
    ],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='death_counter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=r'{ico_path}',
)
"""

spec_path = BASE / "death_counter.spec"
spec_path.write_text(spec.strip(), encoding="utf-8")
print(f"[OK] .spec criado: {spec_path}")

# ── 5. Rodar PyInstaller ───────────────────────────────────────────────────
result = subprocess.run(
    [sys.executable, "-m", "PyInstaller", "--clean", str(spec_path)],
    cwd=str(BASE)
)

if result.returncode == 0:
    exe_dist = BASE / "dist" / "death_counter.exe"
    if exe_dist.exists():
        shutil.copy(exe_dist, BASE / "death_counter.exe")
        print()
        print("=" * 56)
        print("  ✅  death_counter.exe gerado com sucesso!")
        print(f"     {BASE / 'death_counter.exe'}")
        print()
        print("  → Sem terminal: interface fica na bandeja do Windows")
        print("  → Clique duplo no ícone ☠️ da bandeja para abrir o painel")
        print("  → Botão direito na bandeja: Pausar / Fechar")
        print("  → Execute como ADMINISTRADOR para hotkeys no jogo")
        print("=" * 56)
    else:
        print("[ERRO] .exe não encontrado em dist/")
else:
    print("[ERRO] PyInstaller falhou. Veja o log acima.")
