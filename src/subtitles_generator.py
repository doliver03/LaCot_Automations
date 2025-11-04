import os
import whisper
import argparse
from tqdm import tqdm
from pydub import AudioSegment
import math

def format_time(seconds):
    ms = int((seconds % 1) * 1000)
    s = int(seconds)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def dividir_audio(audio_path, duracion_segmento=15*60, inicio=10):
    """
    Divide el audio en partes de CANTIDAD de segundos (por defecto, 15 min),
    saltando los primeros 10 segundos definidos en 'inicio'.
    """
    audio = AudioSegment.from_file(audio_path)
    if inicio > 0:
        print(f"⏩ Saltando los primeros {inicio} segundos de musica para la transcripcion...") 
        audio = audio[inicio * 1000:]  # Recorta los primeros segundos

    duracion_total = len(audio) / 1000
    partes = []
    num_partes = math.ceil(duracion_total / duracion_segmento)
    base_name = os.path.splitext(audio_path)[0]

    os.makedirs("temp_segments", exist_ok=True)
    for i in range(num_partes):
        start_ms = i * duracion_segmento * 1000
        end_ms = min((i + 1) * duracion_segmento * 1000, len(audio))
        segmento = audio[start_ms:end_ms]
        parte_path = f"temp_segments/{os.path.basename(base_name)}_part{i+1}.mp3"
        segmento.export(parte_path, format="mp3")
        partes.append(parte_path)

    return partes


def generar_subtitulos(audio_path, modelo="small"):
    print("🎧 Cargando modelo Whisper...")
    model = whisper.load_model(modelo)

    print(f"🗂 Dividiendo audio si es necesario...")
    partes = dividir_audio(audio_path)
    print(f"🔹 {len(partes)} partes creadas.")

    base_path = os.path.splitext(audio_path)[0]
    srt_final = f"{base_path}_final.srt"
    txt_final = f"{base_path}_final.txt"

    contador = 1
    offset = 0.0

    with open(srt_final, "w", encoding="utf-8") as srt_file, open(txt_final, "w", encoding="utf-8") as txt_file:
        for i, parte in enumerate(partes, start=1):
            print(f"\n🗣 Transcribiendo parte {i}/{len(partes)}: {parte}")
            result = model.transcribe(parte, task="transcribe",language="es") ## Forzar el idioma a español
            detected_lang = result.get("language", "unknown")
        
            for segment in tqdm(result["segments"], desc=f"🕐 Parte {i}", unit="segmento"):
                start = segment["start"] + offset
                end = segment["end"] + offset
                text = segment["text"].strip()

                srt_file.write(f"{contador}\n{format_time(start)} --> {format_time(end)}\n{text}\n\n")
                txt_file.write(f"{text}\n")
                contador += 1

            offset += result["segments"][-1]["end"]

    print(f"\n✅ Subtítulos finales: {srt_final}")
    print(f"📝 Transcripción final: {txt_final}")
    print(f"🗑 Borrando archivos temporales...")
    for p in partes:
        os.remove(p)
    os.rmdir("temp_segments")
    print("✨ Proceso completado con éxito ✨")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generador automático de subtítulos con Whisper.")
    parser.add_argument("audio", help="Archivo de audio o video de entrada (.mp3, .mp4, etc.)")
    parser.add_argument("--model", default="small", help="Modelo Whisper: tiny, base, small, medium, large")
    args = parser.parse_args()
    generar_subtitulos(args.audio, modelo=args.model)
