#!/usr/bin/env python3
"""
아티클 수집 스크립트
GeekNews와 RSS 피드에서 최신 아티클을 수집합니다.
"""

import json
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import feedparser
from dateutil import parser as date_parser

def collect_geeknews():
    """GeekNews에서 최신 아티클 수집"""
    url = "https://news.hada.io"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        articles = []
        # 최신 50개 아티클 수집
        article_elements = soup.select('.topic_row')[:50]

        for elem in article_elements:
            try:
                # 제목과 링크
                title_elem = elem.select_one('.topic_title a')
                if not title_elem:
                    continue

                title = title_elem.get_text(strip=True)
                link = title_elem['href']

                # 추천수
                upvotes = 0
                upvotes_elem = elem.select_one('.upvotes')
                if upvotes_elem:
                    upvotes_text = upvotes_elem.get_text(strip=True)
                    try:
                        upvotes = int(upvotes_text.split()[0])
                    except (ValueError, IndexError):
                        upvotes = 0

                # 댓글수
                comments = 0
                comments_elem = elem.select_one('.comments')
                if comments_elem:
                    comments_text = comments_elem.get_text(strip=True)
                    try:
                        comments = int(comments_text.split()[0])
                    except (ValueError, IndexError):
                        comments = 0

                # 발행일 (상대적 시간, 오늘 것으로 가정)
                published_at = datetime.now()

                # 요약 (제목 기반)
                summary = title[:100] + "..." if len(title) > 100 else title

                articles.append({
                    'title': title,
                    'url': link,
                    'upvotes': upvotes,
                    'comments': comments,
                    'published_at': published_at.isoformat(),
                    'summary': summary,
                    'source': 'GeekNews'
                })

            except Exception as e:
                print(f"Error parsing article: {e}")
                continue

        return articles

    except Exception as e:
        print(f"Error collecting from GeekNews: {e}")
        return []

def load_processed_urls():
    """이전에 처리된 URL 목록 로드"""
    url_file = os.path.join(os.path.dirname(__file__), '..', '..', 'candidates', 'processed_urls.json')
    if os.path.exists(url_file):
        try:
            with open(url_file, 'r', encoding='utf-8') as f:
                return set(json.load(f))
        except Exception as e:
            print(f"Error loading processed URLs: {e}")
    return set()

def save_processed_urls(urls):
    """처리된 URL 목록 저장"""
    url_file = os.path.join(os.path.dirname(__file__), '..', '..', 'candidates', 'processed_urls.json')
    try:
        with open(url_file, 'w', encoding='utf-8') as f:
            json.dump(list(urls), f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving processed URLs: {e}")

def scrape_geeknews_details(url):
    """GeekNews 상세 페이지에서 추천수와 댓글수 스크래핑"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # 추천수 추출: <span id='tp{id}'>숫자</span>
        upvotes = 0
        # URL에서 ID 추출
        url_match = re.search(r'id=(\d+)', url)
        if url_match:
            topic_id = url_match.group(1)
            upvotes_elem = soup.select_one(f'span#tp{topic_id}')
            if upvotes_elem:
                upvotes_text = upvotes_elem.get_text(strip=True)
                try:
                    upvotes = int(upvotes_text)
                except (ValueError, TypeError):
                    upvotes = 0

        # 댓글수 추출: "댓글 N개" 텍스트에서 추출
        comments = 0
        comments_elem = soup.find('a', text=re.compile(r'댓글\s+\d+개'))
        if comments_elem:
            comments_text = comments_elem.get_text(strip=True)
            comments_match = re.search(r'(\d+)개', comments_text)
            if comments_match:
                try:
                    comments = int(comments_match.group(1))
                except (ValueError, TypeError):
                    comments = 0

        return upvotes, comments

    except Exception as e:
        print(f"Error scraping details from {url}: {e}")
        return 0, 0

def collect_rss_articles():
    """GeekNews RSS에서 아티클 수집 - 개선된 버전"""
    geeknews_rss_url = "https://feeds.feedburner.com/geeknews-feed"

    try:
        feed = feedparser.parse(geeknews_rss_url)
        print(f"Found {len(feed.entries)} entries in GeekNews RSS")
    except Exception as e:
        print(f"Error parsing GeekNews RSS: {e}")
        return []

    # 이전에 처리된 URL 로드
    processed_urls = load_processed_urls()
    print(f"Loaded {len(processed_urls)} previously processed URLs")

    articles = []
    now = datetime.now()
    cutoff_time = now - timedelta(hours=6)  # 6시간 이내 신규 아티클만 수집
    cutoff_time = cutoff_time.replace(tzinfo=None)

    new_urls = set()  # 이번에 처리할 URL들

    for entry in feed.entries[:30]:  # 더 많은 항목 처리 (30개)
        try:
            # URL 중복 체크
            if entry.link in processed_urls:
                continue

            # 발행일 파싱
            published_at = None
            if hasattr(entry, 'published'):
                published_at = date_parser.parse(entry.published)
            elif hasattr(entry, 'updated'):
                published_at = date_parser.parse(entry.updated)
            else:
                continue

            # timezone-naive로 변환하여 비교
            published_at_naive = published_at.replace(tzinfo=None)

            # 6시간 이내 신규 아티클만 처리
            if published_at_naive < cutoff_time:
                continue

            # 요약
            summary = ""
            if hasattr(entry, 'summary'):
                summary = entry.summary[:300] + "..." if len(entry.summary) > 300 else entry.summary
            elif hasattr(entry, 'description'):
                summary = entry.description[:300] + "..." if len(entry.description) > 300 else entry.description

            # 기본 아티클 정보
            article = {
                'title': entry.title,
                'url': entry.link,
                'upvotes': 0,  # 기본값
                'comments': 0,  # 기본값
                'published_at': published_at.isoformat(),
                'summary': summary,
                'source': 'GeekNews'
            }

            # 품질 기반으로 상세 정보 스크래핑 결정
            # 제목에 기술 키워드가 있거나 구조화된 내용이면 상세 정보 수집
            should_scrape = False
            title_lower = entry.title.lower()
            tech_keywords = ['architecture', 'algorithm', 'performance', 'optimization',
                           'framework', 'library', 'api', 'database', 'ai', 'system']

            if any(keyword in title_lower for keyword in tech_keywords):
                should_scrape = True
            elif len(summary) > 200:  # 내용이 풍부한 경우
                should_scrape = True
            elif '•' in summary or '*' in summary or '1.' in summary:  # 구조화된 내용
                should_scrape = True

            # 상세 정보 스크래핑
            if should_scrape:
                upvotes, comments = scrape_geeknews_details(entry.link)
                article['upvotes'] = upvotes
                article['comments'] = comments
                print(f"Scraped details for: {entry.title[:50]}... (👍{upvotes}, 💬{comments})")

            articles.append(article)
            new_urls.add(entry.link)

        except Exception as e:
            print(f"Error parsing RSS entry: {e}")
            continue

    # 처리된 URL 목록 업데이트
    processed_urls.update(new_urls)
    save_processed_urls(processed_urls)

    print(f"Collected {len(articles)} new articles from RSS")
    print(f"Updated processed URLs count: {len(processed_urls)}")

    return articles

def main():
    """메인 수집 함수"""
    print("Starting article collection...")

    # GeekNews 수집
    geeknews_articles = collect_geeknews()
    print(f"Collected {len(geeknews_articles)} articles from GeekNews")

    # RSS 피드 수집
    rss_articles = collect_rss_articles()
    print(f"Collected {len(rss_articles)} articles from RSS feeds")

    # 모든 아티클 합치기
    all_articles = geeknews_articles + rss_articles

    # 저장
    output_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'candidates')
    os.makedirs(output_dir, exist_ok=True)

    output_file = os.path.join(output_dir, 'collected_articles.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_articles, f, ensure_ascii=False, indent=2)

    print(f"Saved {len(all_articles)} articles to {output_file}")

if __name__ == "__main__":
    main()
