#!/usr/bin/env python3
"""
clip_generator.py
Genera clips desde un archivo de video o audio.

Modos:
 - fixed: corta clips cada N segundos
 - silence: detecta segmentos no-silenciosos y genera clips
 - highlights: usa un .srt o .txt (transcripción) para elegir segmentos 'interesantes'
"""
from PIL import Image, ImageFilter, ImageDraw
import numpy as np
from moviepy.editor import CompositeVideoClip, ColorClip, vfx


import sys, os
sys.path.append(os.path.join(os.getcwd(), "venv", "Lib", "site-packages"))

import argparse
import math
from moviepy.editor import (
    VideoFileClip,
    AudioFileClip,
    CompositeVideoClip,
    ColorClip,
    vfx
)
from pydub import AudioSegment, silence


# === Función para asegurarse que la carpeta exista===
def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

# === Efecto difuminado y fondo con fade radial ===
def aplicar_marco_difuminado(clip):
    try:
        def blur_frame(get_frame, t):
            frame = get_frame(t)
            img = Image.fromarray(frame)
            # 1) Se puede aumentar la escala aquí para reducir el marco (antes 1.0, se deja igual)
            img = img.resize((int(img.width * 1.0), int(img.height * 1.0)))
            blurred = img.filter(ImageFilter.GaussianBlur(radius=28))  # borrosidad del fondo
            return np.array(blurred)

        fondo = clip.fl(lambda gf, t: blur_frame(gf, t))
        fondo = fondo.fx(vfx.colorx, 0.45)

        mask_size = (fondo.w, fondo.h)
        mask = Image.new("L", mask_size, 255)
        draw = ImageDraw.Draw(mask)

        # 2) grad_radius controla el radio máximo del degradado.
        # Reducirlo hace la zona central más grande => marco más delgado.
        # Antes: grad_radius = min(mask_size) // 2
        grad_radius = int(min(mask_size) * 0.42)  # ejemplo: 42% del menor lado (ajusta a 0.36..0.5)

        center = (mask_size[0] // 2, mask_size[1] // 2)
        # También se puede ajustar el paso de -10 a -8 para un degradado más fino
        for r in range(grad_radius, 0, -8):
            alpha = int(255 * (r / grad_radius) ** 2)
            draw.ellipse(
                [center[0] - r, center[1] - r, center[0] + r, center[1] + r],
                fill=alpha
            )
        fade_mask = np.array(mask) / 255.0

        def apply_fade(get_frame, t):
            frame = get_frame(t).astype(np.float32) / 255.0
            return np.uint8(frame * fade_mask[:, :, None] * 255)

        fondo = fondo.fl(apply_fade)

        capa_oscura = ColorClip(size=fondo.size, color=(0, 0, 0), duration=clip.duration).set_opacity(0.55)

        # 3) Cambiar aquí la escala del clip centrado: 0.68 -> 0.75 (más grande => marco más estrecho)
        clip_centrado = clip.resize(0.75).set_position("center")

        final = CompositeVideoClip([fondo, capa_oscura, clip_centrado])
        return final

    except Exception as e:
        print(f"⚠️ Error aplicando efecto difuminado: {e}")
        return clip

# === MODO 1: CLIPS DE DURACIÓN FIJA ===
def clip_fixed(input_path, output_dir, duracion):
    ensure_dir(output_dir)
    try:
        clip = VideoFileClip(input_path)
        is_video = True
    except Exception:
        clip = AudioFileClip(input_path)
        is_video = False

    total = int(clip.duration)
    idx = 1

    for start in range(0, total, duracion):
        end = min(start + duracion, total)
        out = os.path.join(output_dir, f"clip_fixed_{idx:03d}" + (".mp4" if is_video else ".mp3"))
        sub = clip.subclip(start, end)

        # Si es video → aplicar efecto difuminado
        if is_video:
            sub = aplicar_marco_difuminado(sub)
            sub.write_videofile(out, audio_codec="aac", codec="libx264", verbose=False, logger=None)
        else:
            sub.write_audiofile(out, verbose=False, logger=None)

        print(f"✅ Generado: {out} ({start}s - {end}s)")
        idx += 1

    clip.close()

# === MODO 2: DETECCIÓN DE SILENCIOS ===
def clip_silence(input_path, output_dir, min_silence_len=500, silence_thresh=None, padding=500, max_clip_len=120):
    ensure_dir(output_dir)
    audio = AudioSegment.from_file(input_path)

    if silence_thresh is None:
        silence_thresh = audio.dBFS - 16
    print(f"🎚 Umbral dinámico de silencio: {silence_thresh:.1f} dBFS")

    nonsilent = silence.detect_nonsilent(audio, min_silence_len=min_silence_len, silence_thresh=silence_thresh)
    if not nonsilent:
        print("⚠️ No se detectaron segmentos con sonido suficiente.")
        return

    print(f"🔎 Segmentos detectados: {len(nonsilent)}")

    # Fusionar segmentos cercanos
    merged = []
    prev_start, prev_end = nonsilent[0]
    for start, end in nonsilent[1:]:
        if start - prev_end < 1000:
            prev_end = end
        else:
            merged.append((prev_start, prev_end))
            prev_start, prev_end = start, end
    merged.append((prev_start, prev_end))

    print(f"✅ Segmentos fusionados: {len(merged)}")

    is_video = False
    try:
        clip = VideoFileClip(input_path)
        is_video = True
    except Exception:
        clip = AudioFileClip(input_path)

    idx = 1
    for start_ms, end_ms in merged:
        start_ms = max(0, start_ms - padding)
        end_ms = min(len(audio), end_ms + padding)
        start_s, end_s = start_ms / 1000, end_ms / 1000
        dur = end_s - start_s
        if dur < 2:
            continue

        parts = math.ceil(dur / max_clip_len)
        for p in range(parts):
            s = start_s + p * max_clip_len
            e = min(s + max_clip_len, end_s)
            outname = os.path.join(output_dir, f"clip_silence_{idx:03d}" + (".mp4" if is_video else ".mp3"))

            sub = clip.subclip(s, e)
            if is_video:
                sub = aplicar_marco_difuminado(sub)
                sub.write_videofile(outname, audio_codec="aac", codec="libx264", verbose=False, logger=None)
            else:
                sub.write_audiofile(outname, verbose=False, logger=None)
            print(f"🎬 Generado: {outname} ({s:.1f}s - {e:.1f}s)")
            idx += 1

    clip.close()

# === PARSEO DE ARCHIVOS .SRT ===
def parse_srt(srt_path):
    items = []
    if not os.path.exists(srt_path):
        return items
    with open(srt_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read().strip().split("\n\n")
    import re
    time_re = re.compile(r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})")

    def to_seconds(t):
        h, m, rest = t.split(":")
        s, ms = rest.split(",")
        return int(h)*3600 + int(m)*60 + int(s) + int(ms)/1000.0

    for block in content:
        lines = block.strip().splitlines()
        if len(lines) >= 2:
            m = time_re.search(lines[1])
            if m:
                start = to_seconds(m.group(1))
                end = to_seconds(m.group(2))
                text = " ".join(lines[2:]) if len(lines) > 2 else ""
                items.append((start, end, text))
    return items

# === MODO 3: CLIPS DESTACADOS SEGÚN SRT ===
def clip_highlights(input_path, srt_path, output_dir, clip_padding=3, top_k=6, keywords=None):
    ensure_dir(output_dir)
    segments = parse_srt(srt_path)
    if not segments:
        print("⚠️ No se encontró SRT o está vacío.")
        return

    scored = []
    for (start, end, text) in segments:
        score = len(text.split())
        if keywords:
            for kw in keywords:
                if kw.lower() in text.lower():
                    score += 100
        scored.append((score, start, end, text))

    scored.sort(reverse=True, key=lambda x: x[0])
    chosen = scored[:top_k]

    idx = 1
    for score, start, end, text in chosen:
        s = max(0, start - clip_padding)
        e = end + clip_padding
        outname = os.path.join(output_dir, f"clip_high_{idx:03d}.mp4")
        try:
            v = VideoFileClip(input_path)
            sub = v.subclip(s, e)
            sub = aplicar_marco_difuminado(sub)
            sub.write_videofile(outname, audio_codec="aac", codec="libx264", verbose=False, logger=None)
            v.close()
        except Exception:
            a = AudioFileClip(input_path)
            outname = outname.replace(".mp4", ".mp3")
            sub = a.subclip(s, e)
            sub.write_audiofile(outname, verbose=False, logger=None)
            a.close()
        print(f"✅ Generado: {outname} [{start:.1f}-{end:.1f}] score={score} texto_preview={text[:50]!r}")
        idx += 1

# === MAIN ===
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="Archivo de entrada (.mp4, .mp3, etc.)")
    parser.add_argument("--mode", choices=["fixed", "silence", "highlights"], default="fixed")
    parser.add_argument("--dur", type=int, default=30, help="duración en segundos (modo fixed)")
    parser.add_argument("--out", default="demo/clips", help="carpeta de salida")
    parser.add_argument("--srt", help="ruta a .srt (modo highlights)")
    parser.add_argument("--keywords", help="palabras separadas por coma para priorizar (modo highlights)")
    parser.add_argument("--min_silence_len", type=int, default=700, help="ms min para considerar silencio (silence)")
    parser.add_argument("--silence_thresh", type=int, default=-40, help="dBFS umbral de silencio (silence)")
    args = parser.parse_args()

    if args.mode == "fixed":
        clip_fixed(args.input, args.out, args.dur)
    elif args.mode == "silence":
        clip_silence(args.input, args.out, args.min_silence_len, args.silence_thresh)
    elif args.mode == "highlights":
        kws = args.keywords.split(",") if args.keywords else None
        clip_highlights(args.input, args.srt, args.out, clip_padding=3, top_k=args.dur, keywords=kws)

if __name__ == "__main__":
    main()
