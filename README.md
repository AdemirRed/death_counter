# 💀 Death Counter — Guia de Instalação

## Estrutura de arquivos

```
death_counter/
├── death_counter.py     ← Backend Python (roda esse)
├── obs_overlay.html     ← Fonte do OBS
├── controller.html      ← Painel de controle (abre no navegador)
├── config.json          ← Gerado automaticamente
├── templates/           ← Coloque prints das telas de morte aqui
└── README.md
```

---

## 1. Instalar dependências Python

```bash
pip install flask flask-cors mss pillow pytesseract opencv-python numpy
```

### Tesseract OCR (só se usar detecção por texto)
- **Windows:** https://github.com/UB-Mannheim/tesseract/wiki
- **Linux:** `sudo apt install tesseract-ocr`
- **macOS:** `brew install tesseract`

---

## 2. Rodar o backend

```bash
python death_counter.py
```

Vai aparecer:
```
==================================================
  💀 Death Counter — Backend
==================================================
  Servidor:      http://localhost:8765
  Painel:        http://localhost:8765/
  OBS Overlay:   http://localhost:8765/obs_overlay.html
==================================================
```

---

## 3. Configurar no OBS

1. **Adicionar Fonte → Browser**
2. URL: `http://localhost:8765/obs_overlay.html`
3. Largura: **300** | Altura: **180**
4. ✅ Atualizar navegador quando a cena ficar ativa

### Parâmetros de URL opcionais:
| Parâmetro | Opções |
|-----------|--------|
| `style`   | `dark`, `neon`, `blood`, `light`, `minimal` |
| `pos`     | `topLeft`, `topRight`, `bottomLeft`, `bottomRight`, `center` |
| `size`    | `small`, `normal`, `large` |

**Exemplo:** `http://localhost:8765/obs_overlay.html?style=neon&pos=bottomRight`

---

## 4. Painel de Controle

Abra no navegador: **http://localhost:8765**

- **Botão +1 MORTE** — adiciona manualmente
- **Desfazer** — remove a última (erro)
- **Reset** — zera o contador
- **Aba Detecção** — configura OCR ou template matching
- **Aba Templates** — instrui onde colocar as imagens

---

## 5. Detecção Automática

### Opção A: OCR (texto na tela)
- Funciona com qualquer jogo que mostre texto na tela de morte
- Configure as palavras-chave (ex: `YOU DIED, GAME OVER, WASTED`)
- Requer Tesseract instalado

### Opção B: Template Matching (imagem)
1. Tire um print da tela de morte do jogo
2. Copie o arquivo para a pasta `templates/`
3. Ajuste o limiar de confiança (padrão: 0.85)

---

## Hotkeys (opcional — via AutoHotkey ou xdotool)

Você pode criar atalhos de teclado que chamam a API:

```
POST http://localhost:8765/deaths/increment  → +1 morte
POST http://localhost:8765/deaths/decrement  → -1 morte
POST http://localhost:8765/deaths/reset      → zerar
```

**Exemplo com curl:**
```bash
curl -X POST http://localhost:8765/deaths/increment
```

---

## Resolução de problemas

| Problema | Solução |
|----------|---------|
| OBS mostra branco | Verifique se o Python está rodando |
| OCR não detecta | Instale o Tesseract e configure o caminho |
| Template não detecta | Aumente a região de captura ou reduza o limiar |
| Porta em uso | Edite `config.json` e mude a porta |
