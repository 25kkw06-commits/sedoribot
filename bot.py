import os
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
import database  # 데이터베이스 관리 파일 임포트
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import time

# --- 초기 설정 ---
load_dotenv()
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')
DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# 유튜브 API 서비스 생성
try:
    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
except Exception as e:
    print(f"오류: 유튜브 API 서비스 생성 실패. API 키를 확인하세요. ({e})")
    exit()

# 각 유튜브 채널별 마지막 영상 ID를 저장할 딕셔너리 (봇 실행 중에만 유지됨)
last_video_ids = {}

# --- 봇 이벤트 ---
@bot.event
async def on_ready():
    print(f'{bot.user.name} 봇이 준비되었습니다.')
    print('------------------------------------')
    # 슬래시 명령어 동기화
    await bot.tree.sync()
    # 백그라운드 작업 시작
    check_youtube_updates.start()

# --- 슬래시 명령어 ---
@bot.tree.command(name="알림추가", description="이 채널에 특정 유튜버의 새 영상 알림을 추가합니다.")
async def add_alert(interaction: discord.Interaction, youtube_channel_id: str):
    if not youtube_channel_id.startswith("UC"):
        await interaction.response.send_message("❌ 잘못된 유튜브 채널 ID 형식입니다. 'UC'로 시작해야 합니다.", ephemeral=True)
        return

    success = database.add_subscription(interaction.guild.id, interaction.channel.id, youtube_channel_id)
    if success:
        await interaction.response.send_message(f"✅ **{youtube_channel_id}** 채널의 알림을 추가했습니다!")
    else:
        await interaction.response.send_message("❌ 이미 이 채널에 등록된 알림입니다.", ephemeral=True)

@bot.tree.command(name="알림제거", description="이 채널에서 특정 유튜버의 알림을 제거합니다.")
async def remove_alert(interaction: discord.Interaction, youtube_channel_id: str):
    success = database.remove_subscription(interaction.channel.id, youtube_channel_id)
    if success:
        await interaction.response.send_message(f"🗑️ **{youtube_channel_id}** 채널의 알림을 제거했습니다.")
    else:
        await interaction.response.send_message("❌ 이 채널에 등록되지 않은 알림입니다.", ephemeral=True)

# --- 백그라운드 작업 (핵심 로직) ---
@tasks.loop(minutes=5)
async def check_youtube_updates():
    print("\n[INFO] 유튜브 채널 업데이트 확인 시작...")
    all_yt_channels = database.get_all_youtube_channels()
    
    if not all_yt_channels:
        print("[INFO] 등록된 유튜브 채널이 없습니다.")
        return

    print(f"[INFO] 확인할 채널 목록: {all_yt_channels}")

    for yt_channel_id in all_yt_channels:
        try:
            # 최신 영상 정보 가져오기 (이전 코드와 유사)
            request = youtube.search().list(part="snippet", channelId=yt_channel_id, maxResults=1, order="date")
            response = request.execute()

            if 'items' in response and len(response['items']) > 0:
                latest_video = response['items'][0]
                video_id = latest_video['id']['videoId']
                
                # 이전에 확인한 영상 ID와 비교
                last_id = last_video_ids.get(yt_channel_id)
                if last_id != video_id:
                    print(f"[!!] 새 영상 발견: {yt_channel_id} - {latest_video['snippet']['title']}")
                    last_video_ids[yt_channel_id] = video_id # 최신 ID로 업데이트

                    if last_id is not None: # 봇이 처음 켜진게 아니라면 알림 발송
                        # 이 유튜버를 구독하는 모든 디스코드 채널에 알림 보내기
                        subscribers = database.get_subscribers(yt_channel_id)
                        for discord_channel_id in subscribers:
                            channel = bot.get_channel(discord_channel_id)
                            if channel:
                                # Embed 메시지 생성 및 전송
                                embed = create_video_embed(latest_video)
                                await channel.send(embed=embed)
            time.sleep(1) # API 요청 사이에 약간의 딜레이
        except HttpError as e:
            print(f"오류: {yt_channel_id} 채널 확인 중 API 에러 발생 (HTTP {e.resp.status})")
        except Exception as e:
            print(f"오류: {yt_channel_id} 채널 확인 중 예상치 못한 문제 발생 ({e})")

@check_youtube_updates.before_loop
async def before_check():
    """루프가 시작되기 전에 봇이 준비될 때까지 기다립니다."""
    await bot.wait_until_ready()
    # 시작 시 DB에 있는 채널들의 마지막 영상 ID를 미리 로드
    print("[INFO] 초기 영상 ID를 로드합니다...")
    all_yt_channels = database.get_all_youtube_channels()
    for yt_channel_id in all_yt_channels:
        # 로직은 생략. 간단하게는 그냥 빈 상태로 시작해도 무방.
        # 정교하게 하려면 시작 시 각 채널의 최신 영상을 가져와서 last_video_ids에 저장.
        pass
    print("[INFO] 로드 완료.")


def create_video_embed(video_data):
    """알림에 사용할 Embed 객체를 생성합니다."""
    snippet = video_data['snippet']
    video_id = video_data['id']['videoId']
    video_url = f"https://www.youtube.com/watch?v={video_id}"

    embed = discord.Embed(
        title=f"🎬 {snippet['title']}",
        url=video_url,
        description="위 제목을 클릭하면 영상으로 바로 이동합니다.",
        color=0xFF0000 # 빨간색
    )
    embed.set_author(name=f"{snippet['channelTitle']} 채널에 새 영상이 업로드되었습니다!")
    embed.set_image(url=snippet['thumbnails']['high']['url'])
    embed.set_footer(text="YouTube 알림 봇")
    return embed

# --- 봇 실행 ---
if __name__ == "__main__":
    database.init_db()  # 프로그램 시작 시 데이터베이스 파일이 없으면 생성
    bot.run(DISCORD_BOT_TOKEN)
# bot.py 파일의 맨 아래, 기존 코드 밑에 추가
from flask import Flask
from threading import Thread

# === 웹서버 유지를 위한 코드 ===
app = Flask('')

@app.route('/')
def home():
    return "I'm alive!"

def run():
  app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()
# ==========================


# --- 봇 실행 (수정된 최종 버전) ---
if __name__ == "__main__":
    database.init_db()
    keep_alive() # 웹서버를 먼저 켜고,
    bot.run(DISCORD_BOT_TOKEN) # 그 다음에 봇을 실행