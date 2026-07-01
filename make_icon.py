import os
import shutil
import subprocess
from PIL import Image, ImageDraw

def generate_icon_image(size=512):
    # Create a transparent background
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Padding for the jewel case
    padding = size // 12
    center = size // 2
    
    # 1. Draw the square jewel case (clear plastic container)
    case_bbox = [padding, padding, size - padding, size - padding]
    # Draw transparent grey fill for plastic and a semi-transparent outline
    draw.rounded_rectangle(case_bbox, radius=size//32, fill=(255, 255, 255, 20), outline=(150, 150, 150, 180), width=max(2, size // 64))

    # 2. Draw the white CD inside the case (slightly smaller)
    cd_padding = padding + size // 16
    cd_bbox = [cd_padding, cd_padding, size - cd_padding, size - cd_padding]
    draw.ellipse(cd_bbox, fill=(240, 240, 240, 255), outline=(200, 200, 200, 255), width=max(1, size // 256))

    # 3. Draw the black center hole of the CD
    hole_radius = size // 12
    hole_bbox = [center - hole_radius, center - hole_radius, center + hole_radius, center + hole_radius]
    draw.ellipse(hole_bbox, fill=(20, 20, 20, 255))
    
    # Inner silver ring around the hole
    inner_radius = size // 8
    inner_bbox = [center - inner_radius, center - inner_radius, center + inner_radius, center + inner_radius]
    draw.ellipse(inner_bbox, fill=None, outline=(220, 220, 220, 255), width=max(1, size // 128))

    # 4. Draw the red rectangular tape on the right edge of the jewel case
    rect_width = size // 8
    rect_height = size // 3
    # Align it to the right edge of the case
    rect_x = size - padding - (rect_width // 2)
    rect_y = center - (rect_height // 2)
    rect_bbox = [rect_x, rect_y, rect_x + rect_width, rect_y + rect_height]
    draw.rectangle(rect_bbox, fill=(230, 20, 20, 255))
    
    return img

def generate_icon_png():
    # Size 256 for basic icon generation
    img = generate_icon_image(256)
    # Resize to 22x22 for menu bar, but keep a 2x version for retina (44x44)
    img_retina = img.resize((44, 44), Image.Resampling.LANCZOS)
    img_retina.save('icon.png')
    print("Menu bar icon generated as icon.png")

def generate_icns():
    iconset_dir = "icon.iconset"
    if os.path.exists(iconset_dir):
        shutil.rmtree(iconset_dir)
    os.makedirs(iconset_dir)
    
    base_img = generate_icon_image(1024)
    
    # Standard macOS icon sizes
    sizes = [
        (16, "icon_16x16.png"),
        (32, "icon_16x16@2x.png"),
        (32, "icon_32x32.png"),
        (64, "icon_32x32@2x.png"),
        (128, "icon_128x128.png"),
        (256, "icon_128x128@2x.png"),
        (256, "icon_256x256.png"),
        (512, "icon_256x256@2x.png"),
        (512, "icon_512x512.png"),
        (1024, "icon_512x512@2x.png"),
    ]
    
    for size, name in sizes:
        resized = base_img.resize((size, size), Image.Resampling.LANCZOS)
        resized.save(os.path.join(iconset_dir, name))
        
    # Convert iconset to icns using iconutil
    subprocess.run(["iconutil", "-c", "icns", iconset_dir])
    
    # Clean up the directory
    shutil.rmtree(iconset_dir)
    print("App icon generated as icon.icns")

if __name__ == "__main__":
    generate_icon_png()
    generate_icns()
