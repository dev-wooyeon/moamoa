#!/usr/bin/env python3
"""
아티클 평가 스크립트
수집된 아티클에 평가 모델을 적용합니다.
"""

import json
import os
import re
from datetime import datetime, timedelta

# 코어 토픽 키워드
CORE_TOPICS = [
    'backend', 'database', 'ai', 'system', 'architecture',
    'microservice', 'api', 'cloud', 'devops', 'security',
    'performance', 'scalability', 'distributed', 'algorithm',
    'data structure', 'concurrency', 'network', 'storage'
]

def calculate_score(article):
    """아티클 점수 계산 - 100점 만점 기준 품질 평가"""
    score = 0
    breakdown = {}

    # 1. 기본 점수: 25점 (모든 아티클)
    base_score = 25
    score += base_score
    breakdown['base'] = base_score

    # 2. 제목 품질: 최대 25점
    title_score = 0
    title = article.get('title', '').lower()

    # 기술 키워드 포함도
    tech_keywords = [
        'architecture', 'algorithm', 'performance', 'optimization', 'design',
        'pattern', 'framework', 'library', 'api', 'database', 'cache',
        'concurrency', 'distributed', 'microservice', 'scalability',
        'docker', 'kubernetes', 'aws', 'react', 'vue', 'spring',
        'javascript', 'python', 'java', 'golang', 'rust', 'cpp',
        'machine learning', 'ai', 'deep learning', 'neural network'
    ]

    tech_count = sum(1 for keyword in tech_keywords if keyword in title)
    if tech_count >= 3:
        title_score += 20  # 3개 이상 기술 키워드
    elif tech_count == 2:
        title_score += 12  # 2개 기술 키워드
    elif tech_count == 1:
        title_score += 8   # 1개 기술 키워드

    # 구체적 기술명 보너스
    specific_tech = ['docker', 'kubernetes', 'aws', 'react', 'vue', 'spring', 'tensorflow', 'pytorch']
    specific_count = sum(1 for tech in specific_tech if tech in title)
    if specific_count >= 1:
        title_score += 5

    # 버전/숫자 포함
    if re.search(r'\d+', title):
        title_score += 3

    # 최대값 제한
    title_score = min(title_score, 25)
    score += title_score
    breakdown['title_quality'] = title_score

    # 3. 내용 깊이: 최대 25점
    content_score = 0
    summary = article.get('summary', '')
    content_length = len(summary)

    # 길이 기반 점수
    if content_length >= 800:
        content_score += 15
    elif content_length >= 500:
        content_score += 10
    elif content_length >= 300:
        content_score += 5

    # 구조화된 내용 (목록, 코드 블록 등)
    structure_indicators = ['•', '*', '-', '```', '`', '1.', '2.', '3.']
    structure_count = sum(1 for indicator in structure_indicators if indicator in summary)
    if structure_count >= 5:
        content_score += 10
    elif structure_count >= 3:
        content_score += 7
    elif structure_count >= 1:
        content_score += 4

    # 실제 예제/튜토리얼 포함
    tutorial_keywords = ['example', '예제', '튜토리얼', '가이드', 'how to', 'step by step']
    if any(keyword in summary.lower() for keyword in tutorial_keywords):
        content_score += 5

    # 최대값 제한
    content_score = min(content_score, 25)
    score += content_score
    breakdown['content_depth'] = content_score

    # 4. 실용성: 최대 15점
    practicality_score = 0
    title_lower = article.get('title', '').lower()
    summary_lower = article.get('summary', '').lower()
    content = f"{title_lower} {summary_lower}"

    # 코드 패턴 검색
    code_patterns = [
        r'```[\w]*\n',      # 코드 블록
        r'`[^`]+`',         # 인라인 코드
        r'function\s+\w+',  # 함수 정의
        r'class\s+\w+',     # 클래스 정의
        r'import\s+\w+',    # 임포트
        r'select\s+.*from', # SQL 쿼리
        r'curl\s+',         # API 호출
        r'def\s+\w+',       # Python 함수
        r'const\s+\w+',     # JavaScript 변수
    ]

    code_matches = sum(1 for pattern in code_patterns if re.search(pattern, content, re.IGNORECASE))
    if code_matches >= 5:
        practicality_score += 15
    elif code_matches >= 3:
        practicality_score += 10
    elif code_matches >= 1:
        practicality_score += 6

    # 실무 적용 키워드
    practical_keywords = ['tutorial', 'guide', 'how to', 'best practice', '실무', '적용', 'production', 'deploy']
    if any(keyword in content for keyword in practical_keywords):
        practicality_score += 3

    # 최대값 제한
    practicality_score = min(practicality_score, 15)
    score += practicality_score
    breakdown['practicality'] = practicality_score

    # 5. 주제 관련성: 10점
    topic_score = 0
    if any(topic in content for topic in CORE_TOPICS):
        topic_score = 10
    else:
        # 관련 기술 토픽 체크
        related_topics = ['frontend', 'backend', 'devops', 'security', 'testing', 'ci/cd']
        if any(topic in content for topic in related_topics):
            topic_score = 5

    score += topic_score
    breakdown['topic_relevance'] = topic_score

    # 6. 최신성: 10점
    recency_score = 0
    try:
        published_at = datetime.fromisoformat(article.get('published_at', ''))
        # 미래 날짜이거나 파싱 오류가 있는 경우 RSS는 최근 것으로 취급
        if article.get('source') == 'GeekNews' and published_at.year >= 2025:
            recency_score = 10  # RSS 아티클은 최근 것으로 가정
        elif datetime.now() - published_at < timedelta(hours=24):
            recency_score = 10
    except (ValueError, TypeError):
        # 날짜 파싱 실패 시 RSS는 최근 것으로 가정
        if article.get('source') == 'GeekNews':
            recency_score = 10

    score += recency_score
    breakdown['recency'] = recency_score

    # 7. 사회적 인지도: 최대 15점
    social_score = 0

    # 추천수 (최대 10점)
    upvotes = article.get('upvotes', 0)
    upvotes_score = min(upvotes * 0.5, 10)

    # 댓글수 (최대 5점)
    comments = article.get('comments', 0)
    comments_score = min(comments * 0.3, 5)

    social_score = upvotes_score + comments_score
    social_score = min(social_score, 15)  # 최대 15점 제한

    score += social_score
    breakdown['social_score'] = social_score

    # 8. 페널티: -10점
    penalty_score = 0
    promotional_keywords = [
        '광고', '프로모션', '스폰서', '무료', '할인', '이벤트',
        '모집', '채용', '구인', '리뷰', '사용기', '후기',
        '인터뷰', '후기', '사용법', '설치법', '구매', '판매'
    ]

    title_content = article.get('title', '').lower()
    if any(keyword in title_content for keyword in promotional_keywords):
        penalty_score = -10
        score += penalty_score
    breakdown['penalty'] = penalty_score

    # 점수 범위 제한 (0-100점)
    score = max(0, min(100, score))

    return score, breakdown

def is_candidate(score):
    """후보 선별 기준 - 40점 이상 후보, 50점 이상 PR 대상"""
    return score >= 40

def main():
    """메인 평가 함수"""
    print("Starting article evaluation...")

    # 수집된 아티클 로드
    input_file = os.path.join(os.path.dirname(__file__), '..', '..', 'candidates', 'collected_articles.json')

    if not os.path.exists(input_file):
        print(f"Input file not found: {input_file}")
        return

    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            articles = json.load(f)
    except Exception as e:
        print(f"Error loading articles: {e}")
        return

    print(f"Evaluating {len(articles)} articles...")

    candidates = []
    evaluations = []

    for article in articles:
        score, breakdown = calculate_score(article)

        evaluation = {
            'article': article,
            'score': score,
            'breakdown': breakdown,
            'is_candidate': is_candidate(score)
        }
        evaluations.append(evaluation)

        if is_candidate(score):
            candidates.append(evaluation)

    # 평가 결과 저장
    output_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'candidates')
    os.makedirs(output_dir, exist_ok=True)

    # 모든 평가 결과
    eval_file = os.path.join(output_dir, 'article_evaluations.json')
    with open(eval_file, 'w', encoding='utf-8') as f:
        json.dump(evaluations, f, ensure_ascii=False, indent=2)

    # 후보 목록
    candidates_file = os.path.join(output_dir, 'candidates.json')
    with open(candidates_file, 'w', encoding='utf-8') as f:
        json.dump(candidates, f, ensure_ascii=False, indent=2)

    print(f"Evaluated {len(articles)} articles")
    print(f"Found {len(candidates)} candidates (score >= 50)")
    print(f"High-score candidates (score >= 80): {len([c for c in candidates if c['score'] >= 80])}")

if __name__ == "__main__":
    main()
