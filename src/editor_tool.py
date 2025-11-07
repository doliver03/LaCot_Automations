import os
from moviepy.editor import (
    VideoFileClip,
    CompositeVideoClip,
    ColorClip,
    TextClip,
    ImageClip,
    vfx,
)

# === Efecto difuminado profesional ===
def aplicar_marco_difuminado(clip, scale=1.2, opacity=0.35):
    """
    Crea un fondo difuminado y oscuro detrás del clip principal.
    scale: agranda el fondo (1.2 = 20% más ancho)
    opacity: nivel de oscuridad del fondo (0 = nada, 1 = negro total)
    """
    fondo = (
        clip.resize(width=clip.w * scale)
        .fx(vfx.colorx, 0.6)  # lo oscurece
    )

    capa_oscura = (
        ColorClip(size=fondo.size, color=(0, 0, 0), duration=clip.duration)
        .set_opacity(opacity)
    )

    final = CompositeVideoClip(
        [fondo, capa_oscura, clip.set_position("center")], size=fondo.size
    )
    return final


# === Función auxiliar: crear formatos ===
def adaptar_formato(clip, formato="vertical"):
    """
    Adapta el clip a distintos formatos:
    - 'vertical': 1080x1920
    - 'cuadrado': 1080x1080
    - 'horizontal': 1920x1080
    """
    if formato == "vertical":
        width, height = 1080, 1920
    elif formato == "cuadrado":
        width, height = 1080, 1080
    else:  # horizontal
        width, height = 1920, 1080

    # Redimensiona manteniendo proporción
    clip_resized = clip.resize(height=height)
    clip_resized = clip_resized.crop(
        width=width,
        height=height,
        x_center=clip_resized.w / 2,
        y_center=clip_resized.h / 2,
    )
    return clip_resized


# === Procesamiento principal ===
def procesar_clips(input_folder, output_folder, logo_path=None, texto=None):
    """
    Toma clips existentes en la carpeta clips_fixed, aplica efectos visuales y exporta 3 versiones para redes sociales:
    vertical (9:16), cuadrado (1:1) y horizontal (16:9).
    """
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    clips = [f for f in os.listdir(input_folder) if f.endswith(".mp4")]
    if not clips:
        print("⚠️ No se encontraron clips en la carpeta:", input_folder)
        return

    for clip_name in clips:
        clip_path = os.path.join(input_folder, clip_name)
        print(f"\n🎬 Procesando {clip_path} ...")

        try:
            clip = VideoFileClip(clip_path)
        except Exception as e:
            print(f"❌ Error cargando {clip_name}: {e}")
            continue

        for formato in ["vertical", "cuadrado", "horizontal"]:
            try:
                clip_formato = adaptar_formato(clip, formato)
                final = aplicar_marco_difuminado(clip_formato)

                # --- Agregar logo png ---
                if logo_path and os.path.exists(logo_path):
                    logo = (
                        ImageClip(logo_path)
                        .set_duration(final.duration)
                        .resize(width=200)
                        .set_pos(("right", "bottom"))
                        .set_opacity(0.85)
                    )
                    final = CompositeVideoClip([final, logo])

                # --- Agregar texto---
                """Configurar texto si se proporciona"""
                if texto:
                    txt = (
                        TextClip(
                            texto,
                            fontsize=60,
                            color="white",
                            font="Arial-Bold",
                            stroke_color="black",
                            stroke_width=2,
                        )
                        .set_duration(final.duration)
                        .set_pos(("center", 50))
                    )
                    final = CompositeVideoClip([final, txt])

                # --- Exportar versión ---
                nombre_salida = clip_name.replace(".mp4", f"_{formato}.mp4")
                out_path = os.path.join(output_folder, nombre_salida)

                print(f"➡️ Exportando {formato} → {out_path}")
                final.write_videofile(
                    out_path, codec="libx264", audio_codec="aac", fps=30, preset="medium"
                )
            except Exception as e:
                print(f"⚠️ Error procesando formato {formato}: {e}")

        print(f"✅ {clip_name} procesado en los tres formatos con éxito.")

    print("\n🎉 Todos los clips están listos en:", output_folder)


# === Ejecución principal ===
def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Editor automático que genera clips optimizados para redes sociales."
    )
    parser.add_argument("input", help="Carpeta con clips generados por clip_generator.py")
    parser.add_argument("--out", default="ready_for_socials", help="Carpeta de salida")
    parser.add_argument("--logo", help="Ruta del logo (PNG transparente)", default=None)
    parser.add_argument("--text", help="Texto que se mostrará arriba del video", default=None)
    args = parser.parse_args()

    procesar_clips(args.input, args.out, args.logo, args.text)


if __name__ == "__main__":
    main()
