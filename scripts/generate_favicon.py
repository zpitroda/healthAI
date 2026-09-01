import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pathlib import Path

def create_healthai_icon(size=512):
    # Create high-res RGBA image
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    
    # Rounded squircle badge
    padding = size * 0.05
    r = size * 0.22
    bbox = [padding, padding, size - padding, size - padding]
    
    # Gradient squircle
    base_badge = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    badge_draw = ImageDraw.Draw(base_badge)
    badge_draw.rounded_rectangle(bbox, radius=r, fill=(255, 255, 255, 255))
    
    gradient = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    for y in range(size):
        for x in range(size):
            t = (x * 0.55 + y * 0.45) / size
            t = max(0.0, min(1.0, t))
            # Lerp from Cyan #00f2fe (0, 242, 254) to Electric Blue #2563eb (37, 99, 235)
            r_c = int(0 * (1 - t) + 30 * t)
            g_c = int(242 * (1 - t) + 100 * t)
            b_c = int(254 * (1 - t) + 240 * t)
            gradient.putpixel((x, y), (r_c, g_c, b_c, 255))
            
    # Apply mask
    badge = Image.composite(gradient, Image.new("RGBA", (size, size), (0, 0, 0, 0)), base_badge)
    
    # Border highlight
    border_layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    b_draw = ImageDraw.Draw(border_layer)
    b_draw.rounded_rectangle(bbox, radius=r, outline=(255, 255, 255, 120), width=max(1, int(size * 0.025)))
    badge = Image.alpha_composite(badge, border_layer)
    
    symbol_layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    s_draw = ImageDraw.Draw(symbol_layer)
    
    cx, cy = size / 2, size / 2
    h_w = size * 0.48   # total width of H
    h_h = size * 0.54   # total height of H
    bar_w = size * 0.13 # bar thickness
    corner_r = bar_w * 0.35
    
    left_x1 = cx - h_w / 2
    left_x2 = left_x1 + bar_w
    right_x2 = cx + h_w / 2
    right_x1 = right_x2 - bar_w
    
    top_y = cy - h_h / 2
    bot_y = cy + h_h / 2
    
    color_symbol = (5, 15, 24, 255) # Deep navy #050f18 matching brand UI dark bg
    
    # Draw left vertical bar
    s_draw.rounded_rectangle([left_x1, top_y, left_x2, bot_y], radius=corner_r, fill=color_symbol)
    # Draw right vertical bar
    s_draw.rounded_rectangle([right_x1, top_y, right_x2, bot_y], radius=corner_r, fill=color_symbol)
    
    # Horizontal crossbar
    cross_h = bar_w * 0.95
    cross_y1 = cy - cross_h / 2
    cross_y2 = cy + cross_h / 2
    s_draw.rounded_rectangle([left_x1, cross_y1, right_x2, cross_y2], radius=corner_r, fill=color_symbol)
    
    # In center of crossbar, draw a crisp white medical cross
    spark_w = bar_w * 0.44
    spark_len = bar_w * 1.25
    s_draw.rounded_rectangle(
        [cx - spark_w/2, cy - spark_len/2, cx + spark_w/2, cy + spark_len/2],
        radius=spark_w * 0.3,
        fill=(255, 255, 255, 255)
    )
    s_draw.rounded_rectangle(
        [cx - spark_len/2, cy - spark_w/2, cx + spark_len/2, cy + spark_w/2],
        radius=spark_w * 0.3,
        fill=(255, 255, 255, 255)
    )
    
    # Composite symbol onto badge
    final_img = Image.alpha_composite(badge, symbol_layer)
    return final_img

def generate_all_icons():
    out_dir = Path("l:/healthAI/app/static")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # High-res master icon (1024x1024)
    master = create_healthai_icon(1024)
    
    # Favicon ICO with multiple sizes
    ico_sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    ico_images = [master.resize(s, Image.Resampling.LANCZOS) for s in ico_sizes]
    
    # Save favicon.ico
    ico_path = out_dir / "favicon.ico"
    ico_images[0].save(
        ico_path,
        format="ICO",
        sizes=ico_sizes,
        append_images=ico_images[1:]
    )
    print(f"Saved {ico_path}")
    
    # Save standard PNGs
    master.resize((16, 16), Image.Resampling.LANCZOS).save(out_dir / "favicon-16x16.png")
    master.resize((32, 32), Image.Resampling.LANCZOS).save(out_dir / "favicon-32x32.png")
    master.resize((48, 48), Image.Resampling.LANCZOS).save(out_dir / "favicon-48x48.png")
    master.resize((180, 180), Image.Resampling.LANCZOS).save(out_dir / "apple-touch-icon.png")
    master.resize((192, 192), Image.Resampling.LANCZOS).save(out_dir / "android-chrome-192x192.png")
    master.resize((512, 512), Image.Resampling.LANCZOS).save(out_dir / "android-chrome-512x512.png")
    print("PNG icons generated.")

if __name__ == "__main__":
    generate_all_icons()
