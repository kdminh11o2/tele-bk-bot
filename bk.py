import os
import logging
import time
import tempfile
import shutil
import asyncio
from logging.handlers import RotatingFileHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.error import BadRequest, Conflict
from PIL import Image, ImageEnhance
import pillow_heif
from fastapi import FastAPI
import uvicorn
import threading

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Telegram bot is running"}

def run_fastapi():
    uvicorn.run(app, host="0.0.0.0", port=8080)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        RotatingFileHandler('bot.log', maxBytes=3*1024*1024, backupCount=3),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def process_image(input_path, logo_paths, output_path, crop_type='square', logo_positions=None, opacities=None, logo_choice=None):
    try:
        logger.info(f"Processing image: input={input_path}, logos={logo_paths}, output={output_path}, crop={crop_type}, positions={logo_positions}, opacities={opacities}, logo_choice={logo_choice}")
        
        if not os.path.exists(input_path):
            logger.error(f"Input image file does not exist: {input_path}")
            return False, "Input image file does not exist."
        
        for logo_path in logo_paths:
            logger.info(f"Absolute logo path: {os.path.abspath(logo_path)}")
            if not os.path.exists(logo_path):
                logger.error(f"Logo file does not exist: {logo_path}")
                return False, f"Logo file does not exist: {logo_path}"
        
        if logo_paths == [] and logo_positions == [] and opacities == [] and logo_choice == 'no_logo':
            if input_path.lower().endswith('.heic'):
                logger.info("Detected HEIC file, converting to RGBA")
                try:
                    heif_file = pillow_heif.read_heif(input_path)
                    img = Image.frombytes(
                        heif_file.mode,
                        heif_file.size,
                        heif_file.data,
                        "raw",
                        heif_file.mode,
                        heif_file.stride,
                    ).convert('RGBA')
                except Exception as e:
                    logger.error(f"Error processing HEIC file: {str(e)}")
                    return False, f"Error processing HEIC file: {str(e)}"
            else:
                try:
                    img = Image.open(input_path).convert('RGBA')
                except Exception as e:
                    logger.error(f"Error opening input image: {e}")
                    return False, f"Error opening input image: {str(e)}"
            
            width, height = img.size
            min_dimension = 1200
            target_dimension = 1920
            if crop_type == 'square':
                new_size = min(width, height)
                left = (width - new_size) // 2
                top = (height - new_size) // 2
                img = img.crop((left, top, left + new_size, top + new_size))
                if new_size >= target_dimension:
                    target_size = (target_dimension, target_dimension)
                else:
                    target_size = (max(new_size, min_dimension), max(new_size, min_dimension))
            elif crop_type == '4:5':
                target_ratio = 4/5
                if width/height > target_ratio:
                    new_width = int(height * target_ratio)
                    left = (width - new_width) // 2
                    img = img.crop((left, 0, left + new_width, height))
                    if height >= target_dimension:
                        new_width = int(target_dimension * target_ratio)
                        target_size = (new_width, target_dimension)
                    else:
                        if height < min_dimension:
                            new_width = int(min_dimension * target_ratio)
                            target_size = (new_width, min_dimension)
                        else:
                            target_size = (new_width, height)
                else:
                    new_height = int(width / target_ratio)
                    top = (height - new_height) // 2
                    img = img.crop((0, top, width, top + new_height))
                    if width >= target_dimension:
                        new_height = int(target_dimension / target_ratio)
                        target_size = (target_dimension, new_height)
                    else:
                        if width < min_dimension:
                            new_height = int(min_dimension / target_ratio)
                            target_size = (min_dimension, new_height)
                        else:
                            target_size = (width, new_height)
            else:
                if max(width, height) >= target_dimension:
                    if width > height:
                        new_width = target_dimension
                        new_height = int(height * target_dimension / width)
                    else:
                        new_height = target_dimension
                        new_width = int(width * target_dimension / height)
                    target_size = (new_width, new_height)
                else:
                    if max(width, height) < min_dimension:
                        if width > height:
                            new_width = min_dimension
                            new_height = int(height * min_dimension / width)
                        else:
                            new_height = min_dimension
                            new_width = int(width * min_dimension / height)
                        target_size = (new_width, new_height)
                    else:
                        target_size = (width, height)
            
            if target_size != img.size:
                img = img.resize(target_size, Image.LANCZOS)
            
            img = img.convert('RGB')
            logger.info(f"Saving output file as JPG to {output_path} without logo")
            img.save(output_path, 'JPEG', quality=98, optimize=True)
            return True, "Image processed successfully without logo."
        
        if input_path.lower().endswith('.heic'):
            logger.info("Detected HEIC file, converting to RGBA")
            try:
                heif_file = pillow_heif.read_heif(input_path)
                img = Image.frombytes(
                    heif_file.mode,
                    heif_file.size,
                    heif_file.data,
                    "raw",
                    heif_file.mode,
                    heif_file.stride,
                ).convert('RGBA')
            except Exception as e:
                logger.error(f"Error processing HEIC file: {str(e)}")
                return False, f"Error processing HEIC file: {str(e)}"
        else:
            try:
                img = Image.open(input_path).convert('RGBA')
            except Exception as e:
                logger.error(f"Error opening input image: {e}")
                return False, f"Error opening input image: {str(e)}"
        
        width, height = img.size
        min_dimension = 1200
        target_dimension = 1920
        if crop_type == 'square':
            new_size = min(width, height)
            left = (width - new_size) // 2
            top = (height - new_size) // 2
            img = img.crop((left, top, left + new_size, top + new_size))
            if new_size >= target_dimension:
                target_size = (target_dimension, target_dimension)
            else:
                target_size = (max(new_size, min_dimension), max(new_size, min_dimension))
        elif crop_type == '4:5':
            target_ratio = 4/5
            if width/height > target_ratio:
                new_width = int(height * target_ratio)
                left = (width - new_width) // 2
                img = img.crop((left, 0, left + new_width, height))
                if height >= target_dimension:
                    new_width = int(target_dimension * target_ratio)
                    target_size = (new_width, target_dimension)
                else:
                    if height < min_dimension:
                        new_width = int(min_dimension * target_ratio)
                        target_size = (new_width, min_dimension)
                    else:
                        target_size = (new_width, height)
            else:
                new_height = int(width / target_ratio)
                top = (height - new_height) // 2
                img = img.crop((0, top, width, top + new_height))
                if width >= target_dimension:
                    new_height = int(target_dimension / target_ratio)
                    target_size = (target_dimension, new_height)
                else:
                    if width < min_dimension:
                        new_height = int(min_dimension / target_ratio)
                        target_size = (min_dimension, new_height)
                    else:
                        target_size = (width, new_height)
        else:
            if max(width, height) >= target_dimension:
                if width > height:
                    new_width = target_dimension
                    new_height = int(height * target_dimension / width)
                else:
                    new_height = target_dimension
                    new_width = int(width * target_dimension / height)
                target_size = (new_width, new_height)
            else:
                if max(width, height) < min_dimension:
                    if width > height:
                        new_width = min_dimension
                        new_height = int(height * min_dimension / width)
                    else:
                        new_height = min_dimension
                        new_width = int(width * min_dimension / height)
                    target_size = (new_width, new_height)
                else:
                    target_size = (width, height)
        
        if target_size != img.size:
            img = img.resize(target_size, Image.LANCZOS)
        
        try:
            img_area = target_size[0] * target_size[1]
            
            for logo_path, logo_position, opacity in zip(logo_paths, logo_positions, opacities or [1.0]*len(logo_paths)):
                logo = Image.open(logo_path).convert('RGBA')
                
                if 'kenh14.png' in logo_path:
                    target_logo_area = img_area * 0.035  # 3.5% for kenh14.png
                elif 'AI.png' in logo_path:
                    target_logo_area = img_area * 0.025  # 2.5% for AI.png
                elif 'gd.png' in logo_path:
                    target_logo_area = img_area * 0.012  # 1.2% for gd.png
                else:
                    target_logo_area = img_area * 0.036  # 3.6% for disoi.png
                
                logger.info(f"Logo: {logo_path}, Target Area: {target_logo_area}, Position: {logo_position}")
                
                scale_factor = (target_logo_area / (logo.width * logo.height)) ** 0.5
                logo_width = int(logo.width * scale_factor)
                logo_height = int(logo.height * scale_factor)
                logo = logo.resize((logo_width, logo_height), Image.LANCZOS)
                
                if opacity < 1.0:
                    alpha = logo.split()[3]
                    alpha = ImageEnhance.Brightness(alpha).enhance(opacity)
                    logo.putalpha(alpha)
                
                img_width, img_height = img.size
                if logo_position == 'top-left':
                    paste_position = (0, 0)
                elif logo_position == 'top-right':
                    paste_position = (img_width - logo_width, 0)
                elif logo_position == 'bottom-left':
                    paste_position = (0, img_height - logo_height)
                elif logo_position == 'bottom-right':
                    paste_position = (img_width - logo_width, img_height - logo_height)
                elif logo_position == 'center':
                    paste_position = ((img_width - logo_width) // 2, (img_height - logo_height) // 2)
                elif logo_position == 'middle-top':
                    paste_position = ((img_width - logo_width) // 2, 0)
                elif logo_position == 'middle-bottom':
                    paste_position = ((img_width - logo_width) // 2, img_height - logo_height)
                else:
                    paste_position = (0, 0)
                
                logger.info(f"Pasting logo at position: {paste_position}")
                img.paste(logo, paste_position, logo)
        except Exception as e:
            logger.error(f"Error processing logo: {e}")
            return False, f"Error processing logo: {str(e)}"
        
        img = img.convert('RGB')
        logger.info(f"Saving output file as JPG to {output_path}")
        img.save(output_path, 'JPEG', quality=98, optimize=True)
        return True, "Image processed successfully."
    except Exception as e:
        logger.error(f"Unknown error processing image: {e}")
        return False, f"Unknown error: {str(e)}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Tôi là AI chỉnh sửa ảnh. Hãy gửi hoặc chuyển tiếp ảnh, tôi sẽ xử lý theo yêu cầu của bạn!\n"
        "Bạn sẽ được chọn cách crop ảnh và loại logo để thêm vào."
    )

def initialize_temp_dir(context):
    if 'temp_dir' in context.user_data:
        shutil.rmtree(context.user_data['temp_dir'], ignore_errors=True)
    context.user_data['temp_dir'] = tempfile.mkdtemp()

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    start_time = time.time()
    message = update.message
    
    if 'media_groups' not in context.user_data:
        context.user_data['media_groups'] = {}
        context.user_data['last_media_time'] = 0
        context.user_data['current_group_id'] = None
        initialize_temp_dir(context)
    
    temp_dir = context.user_data['temp_dir']
    file = None
    base_name = "photo"
    file_name = f"input_{time.time()}.jpg"

    if message.photo:
        photo = message.photo[-1]
        file = await photo.get_file()
    elif message.document and message.document.mime_type and message.document.mime_type.startswith('image/'):
        file = await message.document.get_file()
        file_name = message.document.file_name or f"document_{time.time()}"
        base_name = os.path.splitext(message.document.file_name)[0] if message.document.file_name else "document"
    elif message.forward_from or message.forward_from_chat:
        if message.photo:
            photo = message.photo[-1]
            file = await photo.get_file()
        elif message.document and message.document.mime_type and message.document.mime_type.startswith('image/'):
            file = await message.document.get_file()
            file_name = message.document.file_name or f"document_{time.time()}"
            base_name = os.path.splitext(message.document.file_name)[0] if message.document.file_name else "document"

    if not file:
        await message.reply_text("Vui lòng gửi hoặc chuyển tiếp file ảnh!")
        return

    file_size = file.file_size if hasattr(file, 'file_size') else 0
    if file_size > 30 * 1024 * 1024:  # 30MB
        await message.reply_text("File ảnh quá lớn (tối đa 30MB)!")
        return

    current_time = time.time()
    if current_time - context.user_data['last_media_time'] > 5 or context.user_data['current_group_id'] is None:
        context.user_data['current_group_id'] = str(current_time)
        context.user_data['media_groups'][context.user_data['current_group_id']] = {
            'images': [],
            'chat_id': message.chat_id,
            'crop_asked': False,
            'logo_asked': False,
            'processed': False
        }
    
    group_id = context.user_data['current_group_id']
    context.user_data['last_media_time'] = current_time

    context.user_data['media_groups'][group_id]['images'].append({
        'file': file,
        'file_name': file_name,
        'base_name': base_name,
        'input_path': os.path.join(temp_dir, file_name),
        'output_filename': f"{base_name}_edit.jpg",
        'output_path': os.path.join(temp_dir, f"{base_name}_edit.jpg")
    })
    
    logger.info(f"Added image to group_id={group_id}, total images: {len(context.user_data['media_groups'][group_id]['images'])}")
    
    if not context.user_data['media_groups'][group_id]['crop_asked']:
        await ask_for_crop(context.bot, context.user_data['media_groups'][group_id]['chat_id'], group_id)
        context.user_data['media_groups'][group_id]['crop_asked'] = True

async def ask_for_crop(bot, chat_id, group_id):
    keyboard = [
        [InlineKeyboardButton("Ảnh vuông (Facebook)", callback_data=f"crop_square_{group_id}")],
        [InlineKeyboardButton("Ảnh tỉ lệ 4:5 (Instagram)", callback_data=f"crop_4:5_{group_id}")],
        [InlineKeyboardButton("Giữ nguyên tỉ lệ ảnh", callback_data=f"crop_keep_{group_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await bot.send_message(
        chat_id=chat_id,
        text="CHỌN TỈ LỆ ẢNH:",
        reply_markup=reply_markup
    )

async def ask_for_logo(bot, chat_id, group_id, include_back=False):
    keyboard = [
        [InlineKeyboardButton("Logo Đi soi sao đi", callback_data=f"logo_disoi_{group_id}")],
        [InlineKeyboardButton("Logo Kenh14", callback_data=f"logo_kenh14_{group_id}")],
        [InlineKeyboardButton("Logo G-Dragon x K14", callback_data=f"logo_gd_{group_id}")],
        [InlineKeyboardButton("Logo \"ảnh tạo bởi AI\"", callback_data=f"logo_ai_{group_id}")]
    ]
    if include_back:
        keyboard.append([InlineKeyboardButton("Quay về", callback_data=f"back_to_crop_{group_id}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await bot.send_message(
        chat_id=chat_id,
        text="CHỌN LOGO:",
        reply_markup=reply_markup
    )

async def ask_for_position(bot, chat_id, group_id, logo_type, include_back=False):
    keyboard = [
        [InlineKeyboardButton("Góc trên - trái", callback_data=f"pos_top-left_{group_id}_{logo_type}.png")],
        [InlineKeyboardButton("Góc trên - phải", callback_data=f"pos_top-right_{group_id}_{logo_type}.png")],
        [InlineKeyboardButton("Góc dưới - trái", callback_data=f"pos_bottom-left_{group_id}_{logo_type}.png")],
        [InlineKeyboardButton("Góc dưới - phải", callback_data=f"pos_bottom-right_{group_id}_{logo_type}.png")],
        [InlineKeyboardButton("Ở giữa ảnh - độ mờ tùy chỉnh", callback_data=f"pos_center_{group_id}_{logo_type}.png")],
        [InlineKeyboardButton("Giữa - Phía trên", callback_data=f"pos_middle-top_{group_id}_{logo_type}.png")],
        [InlineKeyboardButton("Giữa - Phía dưới", callback_data=f"pos_middle-bottom_{group_id}_{logo_type}.png")]
    ]
    
    if include_back:
        keyboard.append([InlineKeyboardButton("Quay về", callback_data=f"back_to_logo_{group_id}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await bot.send_message(
        chat_id=chat_id,
        text="CHỌN VỊ TRÍ LOGO:",
        reply_markup=reply_markup
    )

async def ask_for_opacity(bot, chat_id, group_id, logo_type, include_back=False):
    keyboard = [
        [InlineKeyboardButton("Độ mờ 65%", callback_data=f"opacity_0.65_{group_id}_{logo_type}.png")],
        [InlineKeyboardButton("Độ mờ 75%", callback_data=f"opacity_0.75_{group_id}_{logo_type}.png")],
        [InlineKeyboardButton("Độ mờ 85%", callback_data=f"opacity_0.85_{group_id}_{logo_type}.png")],
        [InlineKeyboardButton("Nét 100%", callback_data=f"opacity_1.0_{group_id}_{logo_type}.png")]
    ]
    if include_back:
        keyboard.append([InlineKeyboardButton("Quay về", callback_data=f"back_to_position_{group_id}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await bot.send_message(
        chat_id=chat_id,
        text="CHỌN MỨC ĐỘ MỜ CHO LOGO Ở GIỮA:",
        reply_markup=reply_markup
    )

async def handle_crop_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except BadRequest as e:
        logger.warning(f"Cannot answer CallbackQuery: {str(e)}. Continuing.")
    
    logger.info(f"Received crop selection callback: {query.data}")
    
    callback_data = query.data.split('_')
    if len(callback_data) < 3 or callback_data[0] != 'crop':
        logger.error(f"Invalid crop callback data: {query.data}")
        await query.message.reply_text("Invalid crop selection!")
        cleanup(context)
        return
    
    crop_type = callback_data[1]
    group_id = callback_data[2]
    
    if 'media_groups' not in context.user_data or group_id not in context.user_data['media_groups']:
        logger.error(f"No media group found for group_id={group_id} in handle_crop_selection")
        await query.message.reply_text("No images to process, please send images again!")
        cleanup(context)
        return
    
    try:
        await query.message.delete()
    except BadRequest:
        logger.debug("Cannot delete crop selection message.")
    
    context.user_data['media_groups'][group_id]['crop_type'] = 'square' if crop_type == 'square' else '4:5' if crop_type == '4:5' else 'keep'
    context.user_data['media_groups'][group_id]['crop_display'] = (
        "Ảnh vuông (Facebook)" if crop_type == 'square' else
        "Ảnh tỉ lệ 4:5 (Instagram)" if crop_type == '4:5' else
        "Giữ nguyên tỉ lệ ảnh"
    )
    
    if not context.user_data['media_groups'][group_id]['logo_asked']:
        logger.info(f"Asking for logo selection for group_id={group_id}")
        await ask_for_logo(context.bot, context.user_data['media_groups'][group_id]['chat_id'], group_id, include_back=True)
        context.user_data['media_groups'][group_id]['logo_asked'] = True

async def handle_logo_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except BadRequest as e:
        logger.warning(f"Cannot answer CallbackQuery: {str(e)}. Continuing.")
    
    logger.info(f"Received logo selection callback: {query.data}, user_data_keys={list(context.user_data.get('media_groups', {}).keys())}")
    
    callback_data = query.data.split('_')
    if len(callback_data) < 2:
        logger.error(f"Invalid logo callback data: {query.data}")
        await query.message.reply_text("Invalid logo selection!")
        cleanup(context)
        return
    
    action = callback_data[0]
    group_id = callback_data[-1]
    
    if 'media_groups' not in context.user_data or group_id not in context.user_data['media_groups']:
        logger.error(f"No media group found for group_id={group_id} in handle_logo_selection")
        await query.message.reply_text("No images to process, please send images again!")
        cleanup(context)
        return
    
    if context.user_data['media_groups'][group_id].get('processed', False):
        logger.info(f"Ignoring duplicate logo callback for group_id={group_id}")
        return
    
    try:
        await query.message.delete()
    except BadRequest:
        logger.debug("Cannot delete logo selection message.")
    
    if action == 'back':
        logger.info(f"User selected back to crop for group_id={group_id}")
        context.user_data['media_groups'][group_id]['logo_choice'] = None
        context.user_data['media_groups'][group_id]['logo_display'] = None
        context.user_data['media_groups'][group_id]['logo_asked'] = False
        await ask_for_crop(context.bot, context.user_data['media_groups'][group_id]['chat_id'], group_id)
        return
    
    if action == 'logo':
        logo_choice = callback_data[1]
        logger.info(f"User selected logo {logo_choice} for group_id={group_id}")
        context.user_data['media_groups'][group_id]['logo_choice'] = logo_choice
        context.user_data['media_groups'][group_id]['logo_display'] = (
            "Logo Đi soi sao đi" if logo_choice == 'disoi' else
            "Logo Kenh14" if logo_choice == 'kenh14' else
            "Logo \"ảnh tạo bởi AI\"" if logo_choice == 'ai' else
            "Logo G-Dragon x K14" if logo_choice == 'gd' else 
            "Unknown logo"
        )
        
        logger.info(f"Asking for position selection for group_id={group_id}, logo={logo_choice}")
        await ask_for_position(context.bot, context.user_data['media_groups'][group_id]['chat_id'], group_id, logo_choice, include_back=True)
        return

async def handle_position_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except BadRequest as e:
        logger.warning(f"Cannot answer CallbackQuery: {str(e)}. Continuing.")
    
    logger.info(f"Received position selection callback: {query.data}, user_data_keys={list(context.user_data.get('media_groups', {}).keys())}")
    
    callback_data = query.data.split('_')
    if len(callback_data) < 2 or callback_data[0] not in ['pos', 'opacity', 'back']:
        logger.error(f"Invalid callback data: {query.data}")
        await query.message.reply_text("Invalid selection!")
        cleanup(context)
        return
    
    if callback_data[0] == 'back':
        group_id = callback_data[-1]
        if 'media_groups' not in context.user_data or group_id not in context.user_data['media_groups']:
            logger.error(f"No media group found for group_id={group_id} in handle_position_selection")
            await query.message.reply_text("No images to process, please send images again!")
            cleanup(context)
            return
        
        try:
            await query.message.delete()
        except BadRequest:
            logger.debug("Cannot delete message.")
        
        if callback_data[1] == 'to-logo':
            logger.info(f"User selected back to logo for group_id={group_id}")
            context.user_data['media_groups'][group_id]['logo_choice'] = None
            context.user_data['media_groups'][group_id]['logo_display'] = None
            context.user_data['media_groups'][group_id]['logo_asked'] = False
            await ask_for_logo(context.bot, context.user_data['media_groups'][group_id]['chat_id'], group_id, include_back=True)
        elif callback_data[1] == 'to-position':
            logger.info(f"User selected back to position for group_id={group_id}")
            logo_choice = context.user_data['media_groups'][group_id]['logo_choice']
            await ask_for_position(context.bot, context.user_data['media_groups'][group_id]['chat_id'], group_id, logo_choice, include_back=True)
        return
    
    if callback_data[0] == 'pos' and callback_data[1] == 'center':
        group_id = callback_data[2]
        logo_type = callback_data[3].split('.')[0]
        
        if 'media_groups' not in context.user_data or group_id not in context.user_data['media_groups']:
            logger.error(f"No media group found for group_id={group_id} in handle_position_selection")
            await query.message.reply_text("No images to process, please send images again!")
            cleanup(context)
            return
        
        try:
            await query.message.delete()
        except BadRequest:
            logger.debug("Cannot delete position selection message.")
        
        context.user_data['media_groups'][group_id]['position'] = 'center'
        context.user_data['media_groups'][group_id]['position_display'] = "Ở giữa ảnh - độ mờ tùy chỉnh"
        
        logger.info(f"Asking for opacity selection for group_id={group_id}, logo={logo_type}")
        await ask_for_opacity(context.bot, context.user_data['media_groups'][group_id]['chat_id'], group_id, logo_type, include_back=True)
        return
    
    if callback_data[0] == 'opacity':
        group_id = callback_data[2]
        logo_type = callback_data[3].split('.')[0]
        opacity = float(callback_data[1])
        
        if 'media_groups' not in context.user_data or group_id not in context.user_data['media_groups']:
            logger.error(f"No media group found for group_id={group_id} in handle_position_selection")
            await query.message.reply_text("No images to process, please send images again!")
            cleanup(context)
            return
        
        if context.user_data['media_groups'][group_id].get('processed', False):
            logger.info(f"Ignoring duplicate callback for group_id={group_id}")
            return
        
        try:
            await query.message.delete()
        except BadRequest:
            logger.debug("Cannot delete opacity selection message.")
        
        position = context.user_data['media_groups'][group_id]['position']
        logo_choice = context.user_data['media_groups'][group_id]['logo_choice']
        logger.info(f"Selected logo_choice: {logo_choice}, position: {position}, opacity: {opacity} for group_id={group_id}")
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        logo_path = os.path.join(script_dir, 'Logo', f"{logo_choice}.png")
        logo_paths = [logo_path]
        logo_positions = [position]
        opacities = [opacity]
        
        position_display = f"Ở giữa - mờ {int(opacity * 100)}%"
        context.user_data['media_groups'][group_id]['position_display'] = position_display
        
        selections = (
            "Bạn đã chọn:\n"
            f"- {context.user_data['media_groups'][group_id]['crop_display']}\n"
            f"- {context.user_data['media_groups'][group_id]['logo_display']}\n"
            f"- {context.user_data['media_groups'][group_id]['position_display']}"
        )
        await query.message.reply_text(selections)
        
        wait_message = await query.message.reply_text("Chờ trong giây lát...")
        
        for img_data in context.user_data['media_groups'][group_id]['images']:
            logger.info(f"Downloading image file to {img_data['input_path']}")
            download_start = time.time()
            try:
                await img_data['file'].download_to_drive(img_data['input_path'])
            except Exception as e:
                logger.error(f"Error downloading image file: {e}")
                await query.message.reply_text("Error downloading image file. Please try again!")
                cleanup(context)
                return
            logger.info(f"Download took {time.time() - download_start:.2f} seconds")
        
        crop_type = context.user_data['media_groups'][group_id].get('crop_type', 'square')
        
        async def process_and_send_image(img_data):
            input_path = img_data['input_path']
            output_path = img_data['output_path']
            output_filename = img_data['output_filename']
            
            process_start = time.time()
            success, error_message = process_image(
                input_path,
                logo_paths,
                output_path,
                crop_type,
                logo_positions,
                opacities,
                logo_choice=logo_choice
            )
            if success:
                logger.info(f"Image processing took {time.time() - process_start:.2f} seconds")
                send_start = time.time()
                with open(output_path, 'rb') as output_file:
                    await query.message.reply_document(document=output_file, filename=output_filename)
                logger.info(f"Sending file took {time.time() - send_start:.2f} seconds")
                return True
            else:
                await query.message.reply_text(f"Error processing image {output_filename}: {error_message}")
                return False
        
        logger.info(f"Processing images for group_id={group_id} with logo {logo_choice} at position {position} with opacity {opacity}")
        tasks = [process_and_send_image(img_data) for img_data in context.user_data['media_groups'][group_id]['images']]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        context.user_data['media_groups'][group_id]['processed'] = all(result is True for result in results if not isinstance(result, Exception))
        
        try:
            await wait_message.delete()
        except BadRequest:
            logger.debug("Cannot delete wait message.")
        
        logger.info(f"Finished processing group_id={group_id}, cleaning up")
        if group_id in context.user_data['media_groups']:
            del context.user_data['media_groups'][group_id]
        if not context.user_data['media_groups']:
            cleanup(context)
        return
    
    # Xử lý các vị trí khác (không phải center)
    group_id = callback_data[2]
    
    if 'media_groups' not in context.user_data or group_id not in context.user_data['media_groups']:
        logger.error(f"No media group found for group_id={group_id} in handle_position_selection")
        await query.message.reply_text("No images to process, please send images again!")
        cleanup(context)
        return
    
    if context.user_data['media_groups'][group_id].get('processed', False):
        logger.info(f"Ignoring duplicate position callback for group_id={group_id}")
        return
    
    try:
        await query.message.delete()
    except BadRequest:
        logger.debug("Cannot delete position selection message.")
    
    position = callback_data[1]
    logo_choice = context.user_data['media_groups'][group_id]['logo_choice']
    logger.info(f"Selected logo_choice: {logo_choice}, position: {position} for group_id={group_id}")
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    logo_path = os.path.join(script_dir, 'Logo', f"{logo_choice}.png")
    logo_paths = [logo_path]
    logo_positions = [position]
    opacities = [1.0]  # Mặc định opacity 1.0 cho các vị trí không phải center
    
    position_display = (
        "Góc trên - trái" if position == 'top-left' else
        "Góc trên - phải" if position == 'top-right' else
        "Góc dưới - trái" if position == 'bottom-left' else
        "Góc dưới - phải" if position == 'bottom-right' else
        "Giữa - Phía trên" if position == 'middle-top' else
        "Giữa - Phía dưới" if position == 'middle-bottom' else
        "Unknown position"
    )
    
    context.user_data['media_groups'][group_id]['position_display'] = position_display
    
    selections = (
        "Bạn đã chọn:\n"
        f"- {context.user_data['media_groups'][group_id]['crop_display']}\n"
        f"- {context.user_data['media_groups'][group_id]['logo_display']}\n"
        f"- {context.user_data['media_groups'][group_id]['position_display']}"
    )
    await query.message.reply_text(selections)
    
    wait_message = await query.message.reply_text("Chờ trong giây lát...")
    
    for img_data in context.user_data['media_groups'][group_id]['images']:
        logger.info(f"Downloading image file to {img_data['input_path']}")
        download_start = time.time()
        try:
            await img_data['file'].download_to_drive(img_data['input_path'])
        except Exception as e:
            logger.error(f"Error downloading image file: {e}")
            await query.message.reply_text("Error downloading image file. Please try again!")
            cleanup(context)
            return
        logger.info(f"Download took {time.time() - download_start:.2f} seconds")
    
    crop_type = context.user_data['media_groups'][group_id].get('crop_type', 'square')
    
    async def process_and_send_image(img_data):
        input_path = img_data['input_path']
        output_path = img_data['output_path']
        output_filename = img_data['output_filename']
        
        process_start = time.time()
        success, error_message = process_image(
            input_path,
            logo_paths,
            output_path,
            crop_type,
            logo_positions,
            opacities,
            logo_choice=logo_choice
        )
        if success:
            logger.info(f"Image processing took {time.time() - process_start:.2f} seconds")
            send_start = time.time()
            with open(output_path, 'rb') as output_file:
                await query.message.reply_document(document=output_file, filename=output_filename)
            logger.info(f"Sending file took {time.time() - send_start:.2f} seconds")
            return True
        else:
            await query.message.reply_text(f"Error processing image {output_filename}: {error_message}")
            return False
    
    logger.info(f"Processing images for group_id={group_id} with logo {logo_choice} at position {position}")
    tasks = [process_and_send_image(img_data) for img_data in context.user_data['media_groups'][group_id]['images']]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    context.user_data['media_groups'][group_id]['processed'] = all(result is True for result in results if not isinstance(result, Exception))
    
    try:
        await wait_message.delete()
    except BadRequest:
        logger.debug("Cannot delete wait message.")
    
    logger.info(f"Finished processing group_id={group_id}, cleaning up")
    if group_id in context.user_data['media_groups']:
        del context.user_data['media_groups'][group_id]
    if not context.user_data['media_groups']:
        cleanup(context)

def cleanup(context: ContextTypes.DEFAULT_TYPE):
    if 'temp_dir' in context.user_data:
        shutil.rmtree(context.user_data['temp_dir'], ignore_errors=True)
    context.user_data.clear()

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")
    if update and update.message and not context.user_data.get('processed', False):
        await update.message.reply_text("An error occurred. Please try again later!")
    cleanup(context)

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    logo_files = ['kenh14.png', 'disoi.png', 'AI.png', 'gd.png']
    logo_dir = os.path.join(script_dir, 'Logo')
    for logo in logo_files:
        logo_path = os.path.join(logo_dir, logo)
        if not os.path.exists(logo_path):
            logger.error(f"Logo file does not exist: {logo_path}. Bot will stop.")
            return
    
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        logger.error("Không tìm thấy TELEGRAM_TOKEN trong biến môi trường.")
        return
    
    fastapi_thread = threading.Thread(target=run_fastapi, daemon=True)
    fastapi_thread.start()
    
    while True:
        try:
            application = Application.builder().token(token).build()
            
            application.add_handler(CommandHandler("start", start))
            application.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, handle_media))
            application.add_handler(CallbackQueryHandler(handle_crop_selection, pattern='^crop_'))
            application.add_handler(CallbackQueryHandler(handle_logo_selection, pattern='^(logo_|back_to_crop_)'))
            application.add_handler(CallbackQueryHandler(handle_position_selection, pattern='^(pos_|opacity_|back_to_logo_|back_to_position_)'))
            application.add_error_handler(error_handler)            
            application.run_polling()
        except Conflict as e:
            logger.error(f"Lỗi Conflict: {str(e)}. Thử khởi động lại sau 5 giây...")
            time.sleep(5)
            continue
        except Exception as e:
            logger.error(f"Lỗi khi khởi động bot: {str(e)}")
            raise

if __name__ == '__main__':
    main()
