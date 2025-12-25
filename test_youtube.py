import os
from yt_dlp import YoutubeDL
import time

url = "https://www.youtube.com/playlist?list=PLbLC5kIdjT_EJEICsvJoWnvWHaGwosBBU"

def get_playlist_info(url):
    ydl_opts = {
        # 从 Firefox 读取 cookies（用于会员/年龄限制等）
        "cookiesfrombrowser": ("firefox",),
        "extract_flat": True,  # 只提取元数据，不下载
        "quiet": True,
    }
    
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        if 'entries' in info:
            return info['entries']
        else:
            # 如果不是播放列表，返回单个视频信息
            return [info]


def download_playlist_with_retry(url, max_retries=3):
    # 获取播放列表信息
    playlist_entries = get_playlist_info(url)
    print(f"Found {len(playlist_entries)} videos in the playlist")
    
    # 创建下载目录
    download_dir = "downloads"
    os.makedirs(download_dir, exist_ok=True)
    
    # 记录每个视频的标题，用于后续验证
    expected_files = []
    for entry in playlist_entries:
        # 清理文件名，使其与 yt-dlp 的处理方式一致
        title = entry.get('title', f"Video_{entry.get('id', 'unknown')}")
        # yt-dlp 会清理文件名中的特殊字符，我们也需要做类似处理
        safe_title = "".join(c for c in title if c.isalnum() or c in (" ", "-", "_", ".")).rstrip()
        expected_files.append(safe_title)
    
    # 显示所有需要下载的文件名
    print("\nFiles to be downloaded:")
    for i, expected_file in enumerate(expected_files, 1):
        print(f"  [P{i:02d}] {expected_file}")
    print()  # 空行分隔
    
    # 定义进度钩子函数
    # Track current video information
    total_videos = len(playlist_entries)
    current_video_info = {'index': 0, 'title': 'Unknown'}
    
    def progress_hook(d):
        nonlocal current_video_info
        if d.get('info_dict'):
            # Update current video info when starting a new video
            title = d['info_dict'].get('title', 'Unknown')
            # Find the index of this video in our playlist
            for i, entry in enumerate(playlist_entries):
                if entry.get('title') == title or entry.get('id') == d['info_dict'].get('id'):
                    current_video_info = {'index': i+1, 'title': title}
                    break
        
        if d['status'] == 'downloading':
            filename = d.get('filename', 'Unknown')
            # 获取文件名（不包含路径）
            file_basename = os.path.basename(filename)
            percent = d.get('_percent_str', 'Unknown')
            speed = d.get('_speed_str', 'Unknown')
            eta = d.get('_eta_str', 'Unknown')
            # Clear the line and print new progress in one line
            print(f"\r  [{current_video_info['index']}/{total_videos}] Downloading: {file_basename} ({percent} at {speed}, ETA: {eta})", end='', flush=True)
        elif d['status'] == 'finished':
            filename = d.get('filename', 'Unknown')
            file_basename = os.path.basename(filename)
            print(f"\r  [{current_video_info['index']}/{total_videos}] Finished: {file_basename}                    ")  # Extra spaces to clear any remaining text
    
    # 尝试下载直到所有视频都成功
    for attempt in range(max_retries + 1):
        print(f"\nDownload attempt {attempt + 1}/{max_retries + 1}")
        
        # Prepare download options
        ydl_opts = {
            # 输出文件名模板 - use playlist index if available
            "outtmpl": f"{download_dir}/[P%(playlist_index)02d] %(title)s.%(ext)s",
            
            # 格式选择：720p 以内的最佳视频 + 最佳音频
            "format": "bestvideo[height<=720]+bestaudio/best[height<=720]",
            
            # 从 Firefox 读取 cookies（用于会员/年龄限制等）
            "cookiesfrombrowser": ("firefox",),
            
            # 播放列表相关（默认就是 True，这里显式写出）
            "noplaylist": False,
            
            # 进度钩子
            "progress_hooks": [progress_hook],
            
            # 安静模式，减少输出（但保留进度）
            "quiet": True,
            "no_warnings": True,
        }
        
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        # 检查下载结果
        downloaded_files = []
        for filename in os.listdir(download_dir):
            if filename.endswith((".mp4", ".mkv", ".webm", ".flv", ".avi", ".mov", ".wmv", ".mp3", ".m4a")):
                # 移除扩展名，只保留文件名
                name_without_ext = os.path.splitext(filename)[0]
                downloaded_files.append(name_without_ext)
        
        # 找出未下载的视频
        missing_files = []
        for expected in expected_files:
            # 检查是否存在匹配的文件（可能扩展名不同）
            found = False
            for downloaded in downloaded_files:
                if downloaded == expected or downloaded.startswith(expected):
                    found = True
                    break
            if not found:
                missing_files.append(expected)
        
        print(f"\nSuccessfully downloaded: {len(downloaded_files)} files")
        print(f"Expected: {len(expected_files)} files")
        print(f"Missing: {len(missing_files)} files")
        
        if not missing_files:
            print("All videos downloaded successfully!")
            break
        else:
            print(f"Missing files: {missing_files}")
            if attempt < max_retries:
                print(f"Retrying missing downloads in 5 seconds...")
                time.sleep(5)
                
                # 重新获取播放列表并下载缺失的视频
                playlist_entries = get_playlist_info(url)
                missing_urls = []
                
                for entry in playlist_entries:
                    title = entry.get('title', f"Video_{entry.get('id', 'unknown')}")
                    safe_title = "".join(c for c in title if c.isalnum() or c in (" ", "-", "_", ".")).rstrip()
                    if safe_title in missing_files:
                        missing_urls.append(entry.get('webpage_url', entry.get('url', f"https://www.youtube.com/watch?v={entry.get('id')}")))
                
                if missing_urls:
                    print(f"Retrying {len(missing_urls)} missing videos...")
                    
                    # 定义用于重试的进度钩子函数
                    def retry_progress_hook(d):
                        if d['status'] == 'downloading':
                            filename = d.get('filename', 'Unknown')
                            # 获取文件名（不包含路径）
                            file_basename = os.path.basename(filename)
                            percent = d.get('_percent_str', 'Unknown')
                            speed = d.get('_speed_str', 'Unknown')
                            eta = d.get('_eta_str', 'Unknown')
                            # For retry, we don't have full playlist info, so just show basic progress
                            print(f"\r  [Retry] Downloading: {file_basename} ({percent} at {speed}, ETA: {eta})", end='', flush=True)
                        elif d['status'] == 'finished':
                            filename = d.get('filename', 'Unknown')
                            file_basename = os.path.basename(filename)
                            print(f"\r  [Retry] Finished: {file_basename}                    ")  # Extra spaces to clear any remaining text
                    
                    # 为重试创建新的下载选项，只下载缺失的视频
                    ydl_opts_retry = {
                        # 输出文件名模板 - use playlist index if available
                        "outtmpl": f"{download_dir}/[P%(playlist_index)02d] %(title)s.%(ext)s",
                        
                        # 格式选择：720p 以内的最佳视频 + 最佳音频
                        "format": "bestvideo[height<=720]+bestaudio/best[height<=720]",
                        
                        # 从 Firefox 读取 cookies（用于会员/年龄限制等）
                        "cookiesfrombrowser": ("firefox",),
                        
                        # 播放列表相关
                        "noplaylist": False,
                        
                        # 进度钩子
                        "progress_hooks": [retry_progress_hook],
                        
                        # 显示更多信息
                        "quiet": False,
                        "no_warnings": False,
                    }
                    
                    with YoutubeDL(ydl_opts_retry) as ydl_retry:
                        ydl_retry.download(missing_urls)
            else:
                print(f"Max retries reached. {len(missing_files)} videos could not be downloaded.")
    
    return len(missing_files) == 0

# Execute the download with retry mechanism
success = download_playlist_with_retry(url)
if success:
    print("\nAll videos in the playlist have been successfully downloaded!")
else:
    print("\nSome videos could not be downloaded after all retry attempts.")
