from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import youtube_dl
import os
import shutil
from pathlib import Path
import logging
import asyncio
import time

# Configuração do logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Adicionar middleware CORS para extensões de navegador
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Montar diretório para arquivos estáticos
app.mount("/static", StaticFiles(directory="static"), name="static")

# Diretório temporário para downloads
DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

# Tempo de expiração dos arquivos em segundos (10 minutos = 600 segundos)
FILE_EXPIRATION_TIME = 600

# HTML para a página inicial
HTML_CONTENT = """
<!DOCTYPE html>
<html>
<head>
    <title>YouTube to MP3 Downloader</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f0f0f0;
        }
        .container {
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        input[type="text"] {
            width: 100%;
            padding: 10px;
            margin: 10px 0;
            border: 1px solid #ddd;
            border-radius: 4px;
        }
        button {
            background-color: #4CAF50;
            color: white;
            padding: 10px 20px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
        }
        button:hover {
            background-color: #45a049;
        }
        #status {
            margin-top: 10px;
            font-weight: bold;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>YouTube to MP3 Downloader</h1>
        <form id="downloadForm" action="/download" method="get">
            <input type="text" id="url" name="url" placeholder="Enter YouTube URL" required>
            <button type="submit">Download MP3</button>
        </form>
        <div id="status"></div>
    </div>
    <script>
        document.getElementById('downloadForm').addEventListener('submit', function(event) {
            const statusDiv = document.getElementById('status');
            statusDiv.textContent = 'Preparando áudio...';
        });
    </script>
</body>
</html>
"""

class DownloadRequest(BaseModel):
    url: str

# Configurações do youtube-dl com proxy e user-agent
YDL_OPTS = {
    'format': 'bestaudio/best',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '320',
    }],
    'outtmpl': str(DOWNLOAD_DIR / '%(title)s.%(ext)s'),
    'noplaylist': True,
    'ffmpeg_location': '/usr/bin/ffmpeg',
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'nocheckcertificate': True,
    'proxy': 'http://sudo.wisp.uno:11870',  # Proxy adicionado
}

# Função para excluir arquivo após um tempo
async def delete_file_after_delay(filepath: Path, delay: int):
    try:
        await asyncio.sleep(delay)
        if filepath.exists():
            filepath.unlink()
            logger.info(f"Deleted file: {filepath}")
    except Exception as e:
        logger.warning(f"Failed to delete file {filepath}: {str(e)}")

@app.get("/", response_class=HTMLResponse)
async def home():
    return HTML_CONTENT

@app.get("/download")
async def download_video(url: str):
    try:
        # Validar URL
        if not url.startswith(('https://www.youtube.com', 'https://youtu.be')):
            raise HTTPException(status_code=400, detail="Invalid YouTube URL")

        # Baixar e converter o vídeo
        with youtube_dl.YoutubeDL(YDL_OPTS) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info).rsplit('.', 1)[0] + '.mp3'
            filepath = Path(filename)

        if not filepath.exists():
            raise HTTPException(status_code=500, detail="Failed to convert to MP3")

        # Iniciar tarefa de exclusão do arquivo após 10 minutos
        asyncio.create_task(delete_file_after_delay(filepath, FILE_EXPIRATION_TIME))

        # Retornar o arquivo
        return FileResponse(
            path=filepath,
            filename=filepath.name,
            media_type='audio/mpeg'
        )

    except Exception as e:
        logger.error(f"Error downloading video: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error downloading video: {str(e)}")

    finally:
        # Limpar arquivos antigos imediatamente após o download
        try:
            current_time = time.time()
            for file in DOWNLOAD_DIR.glob("*.mp3"):
                file_age = current_time - file.stat().st_mtime
                if file_age > FILE_EXPIRATION_TIME:
                    try:
                        file.unlink()
                        logger.info(f"Deleted old file: {file}")
                    except Exception as e:
                        logger.warning(f"Failed to delete old file {file}: {str(e)}")
        except Exception as e:
            logger.warning(f"Error cleaning up old files: {str(e)}")

# Função para limpar o diretório de downloads ao iniciar
@app.on_event("startup")
async def startup_event():
    try:
        # Não tentar excluir a pasta downloads, apenas limpar seu conteúdo
        for file in DOWNLOAD_DIR.glob("*"):
            try:
                if file.is_file():
                    file.unlink()
                elif file.is_dir():
                    shutil.rmtree(file, ignore_errors=True)
                logger.info(f"Deleted {file} during startup")
            except Exception as e:
                logger.warning(f"Failed to delete {file} during startup: {str(e)}")
        # Garantir que a pasta downloads existe
        DOWNLOAD_DIR.mkdir(exist_ok=True)
    except Exception as e:
        logger.warning(f"Error cleaning downloads directory: {str(e)}")

# Função para verificar e limpar arquivos antigos periodicamente
async def cleanup_old_files():
    while True:
        try:
            current_time = time.time()
            for file in DOWNLOAD_DIR.glob("*.mp3"):
                file_age = current_time - file.stat().st_mtime
                if file_age > FILE_EXPIRATION_TIME:
                    try:
                        file.unlink()
                        logger.info(f"Deleted expired file: {file}")
                    except Exception as e:
                        logger.warning(f"Failed to delete expired file {file}: {str(e)}")
        except Exception as e:
            logger.warning(f"Error in periodic cleanup: {str(e)}")
        await asyncio.sleep(300)  # Verifica a cada 5 minutos

# Iniciar tarefa de limpeza periódica
@app.on_event("startup")
async def start_cleanup_task():
    asyncio.create_task(cleanup_old_files())
