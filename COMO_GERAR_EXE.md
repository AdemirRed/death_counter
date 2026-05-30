# Como gerar o death_counter.exe

## Pré-requisitos
Ter o Python instalado com as dependências:
```
python -m pip install pyinstaller flask flask-cors mss pillow numpy opencv-python pytesseract keyboard
```

## Gerar o .exe (um único comando)

Abra o terminal **na pasta do projeto** e rode:

```
python build_exe.py
```

O arquivo `death_counter.exe` será gerado na mesma pasta.

## Ou direto com PyInstaller

```
python -m PyInstaller --onefile --console --name death_counter ^
  --add-data "controller.html;." ^
  --add-data "obs_overlay.html;." ^
  --hidden-import flask ^
  --hidden-import flask_cors ^
  --hidden-import mss ^
  --hidden-import PIL ^
  --hidden-import numpy ^
  --hidden-import cv2 ^
  --hidden-import pytesseract ^
  --hidden-import keyboard ^
  death_counter.py
```

## Executar

1. **Clique com botão direito** em `death_counter.exe`
2. **"Executar como Administrador"** (necessário para hotkeys no jogo)
3. Abra `http://localhost:8765` no navegador

## Distribuir para outras pessoas

Basta enviar:
- `death_counter.exe`
- A pasta `templates/` (se tiver templates salvos)

O `config.json` é gerado automaticamente na primeira execução.
