import os
import random
from typing import List
from urllib.parse import urlencode

import requests
from loguru import logger
from moviepy.video.io.VideoFileClip import VideoFileClip

from app.config import config
from app.models.schema import MaterialInfo, VideoAspect, VideoConcatMode
from app.utils import utils

requested_count = 0

# 跟踪本次视频生成中已使用的本地素材路径
_used_local_materials = set()

def reset_used_local_materials():
    """重置已使用的本地素材跟踪（每次生成视频时调用）"""
    global _used_local_materials
    _used_local_materials = set()

def mark_local_material_used(path: str):
    """标记本地素材为已使用"""
    global _used_local_materials
    _used_local_materials.add(path)

def is_local_material_used(path: str) -> bool:
    """检查本地素材是否已被使用"""
    return path in _used_local_materials


def get_api_key(cfg_key: str):
    api_keys = config.app.get(cfg_key)
    if not api_keys:
        raise ValueError(
            f"\n\n##### {cfg_key} is not set #####\n\nPlease set it in the config.toml file: {config.config_file}\n\n"
            f"{utils.to_json(config.app)}"
        )

    # if only one key is provided, return it
    if isinstance(api_keys, str):
        return api_keys

    global requested_count
    requested_count += 1
    return api_keys[requested_count % len(api_keys)]


def search_videos_pexels(
    search_term: str,
    minimum_duration: int,
    video_aspect: VideoAspect = VideoAspect.portrait,
) -> List[MaterialInfo]:
    aspect = VideoAspect(video_aspect)
    video_orientation = aspect.name
    video_width, video_height = aspect.to_resolution()
    api_key = get_api_key("pexels_api_keys")
    headers = {
        "Authorization": api_key,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
    }
    # Build URL
    params = {"query": search_term, "per_page": 20, "orientation": video_orientation}
    query_url = f"https://api.pexels.com/videos/search?{urlencode(params)}"
    logger.info(f"searching videos: {query_url}, with proxies: {config.proxy}")

    try:
        r = requests.get(
            query_url,
            headers=headers,
            proxies=config.proxy,
            verify=False,
            timeout=(30, 60),
        )
        response = r.json()
        video_items = []
        if "videos" not in response:
            logger.error(f"search videos failed: {response}")
            return video_items
        videos = response["videos"]
        # loop through each video in the result
        for v in videos:
            duration = v["duration"]
            # check if video has desired minimum duration
            if duration < minimum_duration:
                continue
            video_files = v["video_files"]
            # loop through each url to determine the best quality
            for video in video_files:
                w = int(video["width"])
                h = int(video["height"])
                if w == video_width and h == video_height:
                    item = MaterialInfo()
                    item.provider = "pexels"
                    item.url = video["link"]
                    item.duration = duration
                    video_items.append(item)
                    break
        return video_items
    except Exception as e:
        logger.error(f"search videos failed: {str(e)}")

    return []


def search_videos_pixabay(
    search_term: str,
    minimum_duration: int,
    video_aspect: VideoAspect = VideoAspect.portrait,
) -> List[MaterialInfo]:
    aspect = VideoAspect(video_aspect)

    video_width, video_height = aspect.to_resolution()

    api_key = get_api_key("pixabay_api_keys")
    # Build URL
    params = {
        "q": search_term,
        "video_type": "all",  # Accepted values: "all", "film", "animation"
        "per_page": 50,
        "key": api_key,
    }
    query_url = f"https://pixabay.com/api/videos/?{urlencode(params)}"
    logger.info(f"searching videos: {query_url}, with proxies: {config.proxy}")

    try:
        r = requests.get(
            query_url, proxies=config.proxy, verify=False, timeout=(30, 60)
        )
        response = r.json()
        video_items = []
        if "hits" not in response:
            logger.error(f"search videos failed: {response}")
            return video_items
        videos = response["hits"]
        # loop through each video in the result
        for v in videos:
            duration = v["duration"]
            # check if video has desired minimum duration
            if duration < minimum_duration:
                continue
            video_files = v["videos"]
            # loop through each url to determine the best quality
            for video_type in video_files:
                video = video_files[video_type]
                w = int(video["width"])
                # h = int(video["height"])
                if w >= video_width:
                    item = MaterialInfo()
                    item.provider = "pixabay"
                    item.url = video["url"]
                    item.duration = duration
                    video_items.append(item)
                    break
        return video_items
    except Exception as e:
        logger.error(f"search videos failed: {str(e)}")

    return []


def save_video(video_url: str, save_dir: str = "") -> str:
    if not save_dir:
        save_dir = utils.storage_dir("cache_videos")

    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    url_without_query = video_url.split("?")[0]
    url_hash = utils.md5(url_without_query)
    video_id = f"vid-{url_hash}"
    video_path = f"{save_dir}/{video_id}.mp4"

    # if video already exists, return the path
    if os.path.exists(video_path) and os.path.getsize(video_path) > 0:
        logger.info(f"video already exists: {video_path}")
        return video_path

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }

    # if video does not exist, download it
    with open(video_path, "wb") as f:
        f.write(
            requests.get(
                video_url,
                headers=headers,
                proxies=config.proxy,
                verify=False,
                timeout=(60, 240),
            ).content
        )

    if os.path.exists(video_path) and os.path.getsize(video_path) > 0:
        try:
            clip = VideoFileClip(video_path)
            duration = clip.duration
            fps = clip.fps
            clip.close()
            if duration > 0 and fps > 0:
                return video_path
        except Exception as e:
            try:
                os.remove(video_path)
            except Exception:
                pass
            logger.warning(f"invalid video file: {video_path} => {str(e)}")
    return ""


# ==================== 本地素材库混合搜索功能 ====================

def parse_material_tags(filename: str) -> tuple[str, List[str]]:
    """
    解析文件名中的标签
    
    文件名格式：视频名称(标签1,标签2,标签3).扩展名
    
    Args:
        filename: 文件名（不含路径）
    
    Returns:
        (素材名称, 标签列表)
    """
    import re
    # 移除扩展名
    name_without_ext = os.path.splitext(filename)[0]
    
    # 匹配括号中的标签
    pattern = r'^(.+?)\(([^)]+)\)$'
    match = re.match(pattern, name_without_ext)
    
    if match:
        name = match.group(1).strip()
        tags_str = match.group(2)
        # 支持中英文逗号分隔
        tags = [tag.strip() for tag in re.split(r'[,，]', tags_str) if tag.strip()]
        return name, tags
    
    # 如果没有标签格式，返回文件名本身作为名称，空标签列表
    return name_without_ext, []


def scan_local_library(library_dir: str) -> List[dict]:
    """
    扫描本地素材库，解析文件名中的标签
    
    Args:
        library_dir: 本地素材库目录
    
    Returns:
        素材列表，格式：[{"path": "...", "name": "...", "tags": [...], "duration": ...}, ...]
    """
    if not library_dir or not os.path.isdir(library_dir):
        return []
    
    supported_extensions = {'.mp4', '.mov', '.avi', '.flv', '.mkv', '.webm'}
    materials = []
    
    try:
        for filename in os.listdir(library_dir):
            file_path = os.path.join(library_dir, filename)
            
            # 只处理视频文件
            ext = os.path.splitext(filename)[1].lower()
            if ext not in supported_extensions:
                continue
            
            if not os.path.isfile(file_path):
                continue
            
            # 解析文件名和标签
            name, tags = parse_material_tags(filename)
            
            # 获取视频时长
            duration = 0
            try:
                clip = VideoFileClip(file_path)
                duration = clip.duration
                clip.close()
            except Exception:
                pass
            
            materials.append({
                "path": file_path,
                "name": name,
                "tags": tags,
                "duration": duration
            })
        
        logger.info(f"扫描本地素材库完成，共找到 {len(materials)} 个素材")
        return materials
    except Exception as e:
        logger.error(f"扫描本地素材库失败: {str(e)}")
        return []


def match_local_material_with_llm(
    search_term: str,
    local_materials: List[dict]
) -> str:
    """
    使用 LLM 判断本地素材是否匹配搜索条件
    
    Args:
        search_term: 搜索关键词
        local_materials: 本地素材列表
    
    Returns:
        匹配的素材路径，无匹配返回空字符串
    """
    if not local_materials:
        return ""
    
    # 导入 LLM 模块
    from app.services import llm
    
    # 构建素材列表描述
    materials_desc = []
    for i, m in enumerate(local_materials, 1):
        tags_str = ", ".join(m["tags"]) if m["tags"] else "无标签"
        materials_desc.append(f"{i}. {m['name']} - 标签: {tags_str}")
    
    materials_list = "\n".join(materials_desc)
    
    prompt = f"""你是一个视频素材匹配助手。

搜索关键词：{search_term}

本地素材列表：
{materials_list}

请判断哪个素材最匹配搜索关键词。匹配规则：
1. 关键词与素材名称或标签相关即可匹配
2. 支持语义相近的匹配（如 "sky" 匹配 "云", "天空"）
3. 英文关键词可以匹配中文标签，反之亦然

如果有匹配的素材，只返回素材编号（如 "1" 或 "3"）
如果没有任何匹配的素材，只返回 "NONE"

只返回编号或 NONE，不要返回其他任何内容。"""

    try:
        response = llm._generate_response(prompt)
        response = response.strip()
        
        # 检查是否无匹配
        if response.upper() == "NONE":
            logger.info(f"LLM 判断本地素材无匹配: {search_term}")
            return ""
        
        # 尝试解析编号
        try:
            idx = int(response) - 1
            if 0 <= idx < len(local_materials):
                matched = local_materials[idx]
                logger.info(f"LLM 匹配成功: '{search_term}' -> '{matched['name']}'")
                return matched["path"]
        except ValueError:
            pass
        
        logger.warning(f"LLM 返回无效响应: {response}")
        return ""
    except Exception as e:
        logger.error(f"LLM 匹配失败: {str(e)}")
        return ""


def search_videos_hybrid(
    search_term: str,
    minimum_duration: int,
    video_aspect: VideoAspect = VideoAspect.portrait,
    source: str = "pexels"
) -> List[MaterialInfo]:
    """
    混合搜索：优先本地素材库，无匹配则搜索第三方
    
    Args:
        search_term: 搜索关键词
        minimum_duration: 最小时长
        video_aspect: 视频比例
        source: 第三方来源 (pexels/pixabay)
    
    Returns:
        MaterialInfo 列表
    """
    # 检查是否启用混合搜索
    enable_hybrid = config.app.get("enable_hybrid_search", False)
    library_dir = config.app.get("local_material_library", "").strip()
    
    if not enable_hybrid or not library_dir:
        # 未启用混合搜索，直接搜索第三方
        if source == "pixabay":
            return search_videos_pixabay(search_term, minimum_duration, video_aspect)
        return search_videos_pexels(search_term, minimum_duration, video_aspect)
    
    # 扫描本地素材库
    local_materials = scan_local_library(library_dir)
    
    if local_materials:
        # 过滤时长不足的素材和已使用过的素材
        valid_materials = [
            m for m in local_materials 
            if m["duration"] >= minimum_duration and not is_local_material_used(m["path"])
        ]
        
        if valid_materials:
            # 使用 LLM 匹配
            matched_path = match_local_material_with_llm(search_term, valid_materials)
            
            if matched_path:
                # 找到匹配的本地素材
                matched_material = next(
                    (m for m in valid_materials if m["path"] == matched_path), 
                    None
                )
                if matched_material:
                    # 标记为已使用
                    mark_local_material_used(matched_path)
                    item = MaterialInfo()
                    item.provider = "local_library"
                    item.url = matched_path
                    item.duration = int(matched_material["duration"])
                    logger.info(f"使用本地素材: {matched_path}")
                    return [item]
    
    # 本地无匹配，搜索第三方
    logger.info(f"本地素材无匹配，搜索第三方: {source}")
    if source == "pixabay":
        return search_videos_pixabay(search_term, minimum_duration, video_aspect)
    return search_videos_pexels(search_term, minimum_duration, video_aspect)


def download_videos(
    task_id: str,
    search_terms: List[str],
    source: str = "pexels",
    video_aspect: VideoAspect = VideoAspect.portrait,
    video_contact_mode: VideoConcatMode = VideoConcatMode.random,
    audio_duration: float = 0.0,
    max_clip_duration: int = 5,
) -> List[str]:
    # 重置已使用的本地素材跟踪
    reset_used_local_materials()
    
    # 分开存储本地素材和第三方素材，确保本地素材优先
    local_video_items = []
    remote_video_items = []
    valid_video_urls = []
    found_duration = 0.0

    for search_term in search_terms:
        # 使用混合搜索：优先本地素材库，无匹配则搜索第三方
        video_items = search_videos_hybrid(
            search_term=search_term,
            minimum_duration=max_clip_duration,
            video_aspect=video_aspect,
            source=source
        )
        logger.info(f"found {len(video_items)} videos for '{search_term}'")

        for item in video_items:
            if item.url not in valid_video_urls:
                valid_video_urls.append(item.url)
                found_duration += item.duration
                # 根据来源分类
                if item.provider == "local_library":
                    local_video_items.append(item)
                else:
                    remote_video_items.append(item)

    # 合并列表：本地素材在前，第三方素材在后
    # 本地素材随机打乱
    if video_contact_mode.value == VideoConcatMode.random.value:
        random.shuffle(local_video_items)
        random.shuffle(remote_video_items)
    
    # 本地素材优先
    valid_video_items = local_video_items + remote_video_items
    
    logger.info(
        f"found total videos: {len(valid_video_items)} (local: {len(local_video_items)}, remote: {len(remote_video_items)}), "
        f"required duration: {audio_duration} seconds, found duration: {found_duration} seconds"
    )
    video_paths = []

    material_directory = config.app.get("material_directory", "").strip()
    if material_directory == "task":
        material_directory = utils.task_dir(task_id)
    elif material_directory and not os.path.isdir(material_directory):
        material_directory = ""


    total_duration = 0.0
    for item in valid_video_items:
        try:
            # 本地素材库的素材不需要下载，直接使用路径
            if item.provider == "local_library":
                if os.path.exists(item.url):
                    logger.info(f"使用本地素材: {item.url}")
                    video_paths.append(item.url)
                    seconds = min(max_clip_duration, item.duration)
                    total_duration += seconds
                    if total_duration > audio_duration:
                        logger.info(
                            f"total duration: {total_duration} seconds, skip more"
                        )
                        break
                continue
            
            # 第三方素材需要下载
            logger.info(f"downloading video: {item.url}")
            saved_video_path = save_video(
                video_url=item.url, save_dir=material_directory
            )
            if saved_video_path:
                logger.info(f"video saved: {saved_video_path}")
                video_paths.append(saved_video_path)
                seconds = min(max_clip_duration, item.duration)
                total_duration += seconds
                if total_duration > audio_duration:
                    logger.info(
                        f"total duration of downloaded videos: {total_duration} seconds, skip downloading more"
                    )
                    break
        except Exception as e:
            logger.error(f"failed to download video: {utils.to_json(item)} => {str(e)}")
    logger.success(f"downloaded {len(video_paths)} videos")
    return video_paths


if __name__ == "__main__":
    download_videos(
        "test123", ["Money Exchange Medium"], audio_duration=100, source="pixabay"
    )
