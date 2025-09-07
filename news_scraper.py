import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import re
from flask import Flask, jsonify, request
from flask_cors import CORS
import time
import logging
from urllib.parse import urljoin, urlparse
import hashlib
import random
from collections import defaultdict

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Updated news sources with working URLs
NEWS_SOURCES = {
    "hindi": [
        {"name": "Aaj Tak", "url": "https://www.aajtak.in"},
        {"name": "ABP News", "url": "https://www.abplive.com"},
        {"name": "News18 India", "url": "https://hindi.news18.com"},
        {"name": "Zee News", "url": "https://zeenews.india.com"},
        {"name": "India Today", "url": "https://www.indiatoday.in/india"}
    ],
    "kannada": [
        {"name": "TV9 Kannada", "url": "https://tv9kannada.com"},
        {"name": "Public TV", "url": "https://publictv.in"},
        {"name": "NewsFirst Kannada", "url": "https://newsfirstlive.com"},
        {"name": "Kannada Prabha", "url": "https://www.kannadaprabha.com"},
        {"name": "Udayavani", "url": "https://www.udayavani.com"}
    ],
    "bengali": [
        {"name": "News18 Bangla", "url": "https://bengali.news18.com"},
        {"name": "TV9 Bangla", "url": "https://www.tv9bangla.com"},
        {"name": "Zee 24 Ghanta", "url": "https://zeenews.india.com/bengali"},
        {"name": "Anandabazar", "url": "https://www.anandabazar.com"},
        {"name": "Ei Samay", "url": "https://eisamay.indiatimes.com"}
    ]
}

# Comprehensive ministry keywords with proper weighting system
MINISTRY_KEYWORDS = {
    "health": {
        "high_priority": {
            # English
            "health", "hospital", "doctor", "medicine", "medical", "healthcare", "treatment", "disease", "illness", "patient", "clinic", "pharmacy", "vaccination", "vaccine", "covid", "corona", "pandemic", "epidemic",
            # Hindi
            "स्वास्थ्य", "अस्पताल", "डॉक्टर", "दवा", "इलाज", "चिकित्सा", "रोग", "बीमारी", "मरीज", "दवाखाना", "टीकाकरण", "वैक्सीन", "कोविड", "महामारी",
            # Bengali
            "স্বাস্থ্য", "হাসপাতাল", "ডাক্তার", "ওষুধ", "চিকিৎসা", "রোগ", "অসুখ", "রোগী", "ক্লিনিক", "টিকা", "কোভিড", "মহামারী",
            # Kannada
            "ಆರೋಗ್ಯ", "ಆಸ್ಪತ್ರೆ", "ವೈದ್ಯ", "ಔಷಧ", "ಚಿಕಿತ್ಸೆ", "ರೋಗ", "ಅನಾರೋಗ್ಯ", "ರೋಗಿ", "ಕ್ಲಿನಿಕ್", "ಲಸಿಕೆ", "ಕೋವಿಡ್"
        },
        "medium_priority": {
            "nutrition", "diet", "food safety", "mental health", "surgery", "cancer", "diabetes", "heart", "blood pressure",
            "पोषण", "आहार", "खाद्य सुरक्षा", "मानसिक स्वास्थ्य", "शल्यचिकित्सा", "कैंसर", "मधुमेह", "हृदय", "रक्तचाप",
            "পুষ্টি", "খাদ্য", "খাদ্য নিরাপত্তা", "মানসিক স্বাস্থ্য", "শল্যচিকিৎসা", "ক্যান্সার", "ডায়াবেটিস", "হৃদয়", "রক্তচাপ",
            "ಪೋಷಣೆ", "ಆಹಾರ", "ಮಾನಸಿಕ ಆರೋಗ್ಯ", "ಶಸ್ತ್ರಚಿಕಿತ್ಸೆ", "ಕ್ಯಾನ್ಸರ್", "ಮಧುಮೇಹ", "ಹೃದಯ"
        },
        "low_priority": {
            "fitness", "exercise", "vitamin", "protein", "wellness", "hygiene",
            "फिटनेस", "व्यायाम", "विटामिन", "प्रोटीन", "स्वच्छता",
            "ফিটনেস", "ব্যায়াম", "ভিটামিন", "প্রোটিন", "স্বচ্ছতা",
            "ಫಿಟ್ನೆಸ್", "ವ್ಯಾಯಾಮ", "ವಿಟಮಿನ್", "ಪ್ರೋಟೀನ್"
        }
    },
    
    "finance": {
        "high_priority": {
            "finance", "economy", "budget", "tax", "gst", "bank", "banking", "money", "currency", "rupee", "investment", "stock", "market", "inflation", "gdp",
            "वित्त", "अर्थव्यवस्था", "बजट", "कर", "जीएसटी", "बैंक", "बैंकिंग", "पैसा", "मुद्रा", "रुपया", "निवेश", "शेयर", "बाजार", "मुद्रास्फीति",
            "অর্থ", "অর্থনীতি", "বাজেট", "কর", "জিএসটি", "ব্যাংক", "ব্যাংকিং", "টাকা", "মুদ্রা", "বিনিয়োগ", "শেয়ার", "বাজার", "মুদ্রাস্ফীতি",
            "ಹಣಕಾಸು", "ಆರ್ಥಿಕತೆ", "ಬಜೆಟ್", "ತೆರಿಗೆ", "ಬ್ಯಾಂಕ್", "ಹಣ", "ಹೂಡಿಕೆ", "ಮಾರುಕಟ್ಟೆ"
        },
        "medium_priority": {
            "business", "trade", "export", "import", "loan", "credit", "debt", "revenue", "profit", "loss",
            "व्यापार", "व्यवसाय", "निर्यात", "आयात", "ऋण", "क्रेडिट", "आय", "लाभ", "हानि",
            "ব্যবসা", "বাণিজ্য", "রপ্তানি", "আমদানি", "ঋণ", "আয়", "লাভ", "ক্ষতি",
            "ವ್ಯಾಪಾರ", "ರಫ್ತು", "ಆಮದು", "ಸಾಲ", "ಆದಾಯ", "ಲಾಭ"
        },
        "low_priority": {
            "financial", "economic", "fiscal", "monetary", "corporate", "company",
            "वित्तीय", "आर्थिक", "राजकोषीय", "मौद्रिक", "कंपनी",
            "আর্থিক", "আর্থিক", "কোম্পানি",
            "ಆರ್ಥಿಕ", "ಕಂಪನಿ"
        }
    },
    
    "education": {
        "high_priority": {
            "education", "school", "college", "university", "student", "teacher", "exam", "admission", "degree", "scholarship", "learning",
            "शिक्षा", "स्कूल", "कॉलेज", "विश्वविद्यालय", "छात्र", "शिक्षक", "परीक्षा", "प्रवेश", "डिग्री", "छात्रवृत्ति", "अध्ययन",
            "শিক্ষা", "স্কুল", "কলেজ", "বিশ্ববিদ্যালয়", "ছাত্র", "শিক্ষক", "পরীক্ষা", "ভর্তি", "ডিগ্রি", "বৃত্তি", "অধ্যয়ন",
            "ಶಿಕ್ಷಣ", "ಶಾಲೆ", "ಕಾಲೇಜು", "ವಿಶ್ವವಿದ್ಯಾಲಯ", "ವಿದ್ಯಾರ್ಥಿ", "ಶಿಕ್ಷಕ", "ಪರೀಕ್ಷೆ", "ಪ್ರವೇಶ", "ಪದವಿ", "ವಿದ್ಯಾರ್ಥಿವೇತನ"
        },
        "medium_priority": {
            "classroom", "curriculum", "academic", "grade", "result", "mark", "score", "literacy", "research",
            "कक्षा", "पाठ्यक्रम", "शैक्षणिक", "ग्रेड", "परिणाम", "अंक", "साक्षरता", "अनुसंधान",
            "শ্রেণীকক্ষ", "পাঠ্যক্রম", "একাডেমিক", "গ্রেড", "ফলাফল", "নম্বর", "সাক্ষরতা", "গবেষণা",
            "ತರಗತಿ", "ಪಠ್ಯಕ್ರಮ", "ಶೈಕ್ಷಣಿಕ", "ಫಲಿತಾಂಶ", "ಸಂಶೋಧನೆ"
        },
        "low_priority": {
            "knowledge", "skill", "training", "workshop", "seminar",
            "ज्ञान", "कौशल", "प्रशिक्षण", "कार्यशाला", "संगोष्ठी",
            "জ্ঞান", "দক্ষতা", "প্রশিক্ষণ", "কর্মশালা", "সেমিনার",
            "ಜ್ಞಾನ", "ಕೌಶಲ್ಯ", "ತರಬೇತಿ"
        }
    },
    
    "sports": {
        "high_priority": {
            "sports", "cricket", "football", "hockey", "tennis", "badminton", "olympics", "player", "match", "tournament", "game", "championship",
            "खेल", "क्रिकेट", "फुटबॉल", "हॉकी", "टेनिस", "बैडमिंटन", "ओलंपिक", "खिलाड़ी", "मैच", "टूर्नामेंट", "खेल", "चैंपियनशिप",
            "খেলা", "ক্রিকেট", "ফুটবল", "হকি", "টেনিস", "ব্যাডমিন্টন", "অলিম্পিক", "খেলোয়াড়", "ম্যাচ", "টুর্নামেন্ট", "চ্যাম্পিয়নশিপ",
            "ಕ್ರೀಡೆ", "ಕ್ರಿಕೆಟ್", "ಫುಟ್ಬಾಲ್", "ಹಾಕಿ", "ಟೆನ್ನಿಸ್", "ಬ್ಯಾಡ್ಮಿಂಟನ್", "ಒಲಿಂಪಿಕ್ಸ್", "ಆಟಗಾರ", "ಪಂದ್ಯ", "ಟೂರ್ನಮೆಂಟ್"
        },
        "medium_priority": {
            "athlete", "coach", "team", "medal", "winner", "champion", "score", "goal", "run", "wicket",
            "एथलीट", "कोच", "टीम", "पदक", "विजेता", "चैंपियन", "स्कोर", "गोल", "रन", "विकेट",
            "অ্যাথলিট", "কোচ", "দল", "পদক", "বিজয়ী", "চ্যাম্পিয়ন", "স্কোর", "গোল", "রান", "উইকেট",
            "ಅಥ್ಲೀಟ್", "ತರಬೇತುದಾರ", "ತಂಡ", "ಪದಕ", "ವಿಜೇತ", "ಚಾಂಪಿಯನ್", "ಗೋಲ್", "ರನ್"
        },
        "low_priority": {
            "stadium", "ground", "field", "fitness", "training", "practice",
            "स्टेडियम", "मैदान", "फिटनेस", "प्रशिक्षण", "अभ्यास",
            "স্টেডিয়াম", "মাঠ", "ফিটনেস", "প্রশিক্ষণ", "অনুশীলন",
            "ಕ್ರೀಡಾಂಗಣ", "ಮೈದಾನ", "ಫಿಟ್ನೆಸ್", "ತರಬೇತಿ"
        }
    },
    
    "international_affairs": {
        "high_priority": {
            "international", "foreign", "diplomat", "embassy", "visa", "border", "treaty", "agreement", "summit", "bilateral", "multilateral",
            "अंतर्राष्ट्रीय", "विदेशी", "राजदूत", "दूतावास", "वीजा", "सीमा", "संधि", "समझौता", "शिखर सम्मेलन", "द्विपक्षीय",
            "আন্তর্জাতিক", "বিদেশি", "রাষ্ট্রদূত", "দূতাবাস", "ভিসা", "সীমানা", "চুক্তি", "সমঝোতা", "শীর্ষ সম্মেলন", "দ্বিপাক্ষিক",
            "ಅಂತರರಾಷ್ಟ್ರೀಯ", "ವಿದೇಶಿ", "ರಾಯಭಾರಿ", "ದೂತಾವಾಸ", "ವೀಸಾ", "ಗಡಿ", "ಒಪ್ಪಂದ", "ಶೃಂಗಸಭೆ"
        },
        "medium_priority": {
            "china", "pakistan", "america", "usa", "russia", "bangladesh", "nepal", "sri lanka", "trade war", "sanction",
            "चीन", "पाकिस्तान", "अमेरिका", "रूस", "बांग्लादेश", "नेपाल", "श्रीलंका", "व्यापार युद्ध", "प्रतिबंध",
            "চীন", "পাকিস্তান", "আমেরিকা", "রাশিয়া", "বাংলাদেশ", "নেপাল", "শ্রীলঙ্কা", "বাণিজ্য যুদ্ধ", "নিষেধাজ্ঞা",
            "ಚೀನಾ", "ಪಾಕಿಸ್ತಾನ", "ಅಮೇರಿಕಾ", "ರಷ್ಯಾ", "ಬಾಂಗ್ಲಾದೇಶ", "ನೇಪಾಳ", "ಶ್ರೀಲಂಕಾ"
        },
        "low_priority": {
            "global", "world", "united nations", "un", "nato", "g7", "g20",
            "वैश्विक", "विश्व", "संयुक्त राष्ट्र", "जी20",
            "বৈশ্বিক", "বিশ্व", "জাতিসংঘ", "জি২০",
            "ಜಾಗತಿಕ", "ಪ್ರಪಂಚ", "ವಿಶ್ವಸಂಸ್ಥೆ"
        }
    },
    
    "agriculture": {
        "high_priority": {
            "agriculture", "farming", "farmer", "crop", "harvest", "irrigation", "fertilizer", "seed", "pesticide", "soil",
            "कृषि", "खेती", "किसान", "फसल", "कटाई", "सिंचाई", "उर्वरक", "बीज", "कीटनाशक", "मिट्टी",
            "কৃষি", "চাষাবাদ", "কৃষক", "ফসল", "ফসল কাটা", "সেচ", "সার", "বীজ", "কীটনাশক", "মাটি",
            "ಕೃಷಿ", "ಕೃಷಿಕ", "ರೈತ", "ಬೆಳೆ", "ಸುಗ್ಗಿ", "ನೀರಾವರಿ", "ಗೊಬ್ಬರ", "ಬೀಜ", "ಮಣ್ಣು"
        },
        "medium_priority": {
            "rice", "wheat", "cotton", "sugarcane", "msp", "procurement", "subsidy", "rural", "village",
            "चावल", "गेहूं", "कपास", "गन्ना", "एमएसपी", "खरीद", "सब्सिडी", "ग्रामीण", "गांव",
            "চাল", "গম", "তুলা", "আখ", "এমএসপি", "ক্রয়", "ভর্তুকি", "গ্রামীণ", "গ্রাম",
            "ಅಕ್ಕಿ", "ಗೋಧಿ", "ಹತ್ತಿ", "ಕಬ್ಬು", "ಎಂಎಸ್ಪಿ", "ಗ್ರಾಮೀಣ", "ಗ್ರಾಮ"
        },
        "low_priority": {
            "organic", "biotechnology", "gmo", "climate change", "drought", "flood",
            "जैविक", "जैव प्रौद्योगिकी", "जीएमओ", "जलवायु परिवर्तन", "सूखा", "बाढ़",
            "জৈব", "জৈবপ্রযুক্তি", "জিএমও", "জলবায়ু পরিবর্তন", "খরা", "বন্যা",
            "ಸಾವಯವ", "ಜೈವತಂತ್ರಜ್ಞಾನ", "ಹವಾಮಾನ ಬದಲಾವಣೆ", "ಬರಗಾಲ", "ಪ್ರವಾಹ"
        }
    }
}

# Weight values for different priority levels
PRIORITY_WEIGHTS = {
    "high_priority": 5,
    "medium_priority": 3,
    "low_priority": 1
}

class NewsArticle:
    def __init__(self, title, content, url, source, timestamp, ministry=None, language=None, confidence=0.0):
        self.title = title
        self.content = content
        self.url = url
        self.source = source
        self.timestamp = timestamp
        self.ministry = ministry
        self.language = language
        self.confidence = confidence
        # Create unique hash for deduplication
        self.content_hash = hashlib.md5((title.lower().strip()).encode('utf-8')).hexdigest()

    def to_dict(self):
        return {
            "title": self.title,
            "content": self.content,
            "url": self.url,
            "source": self.source,
            "timestamp": self.timestamp,
            "ministry": self.ministry,
            "language": self.language,
            "confidence": round(self.confidence, 2)
        }

class NewsScraper:
    def __init__(self):
        # Rotate user agents to avoid blocking
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        ]
        
        self.headers = {
            'User-Agent': random.choice(user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.seen_articles = set()

    def categorize_by_ministry(self, title, content):
        """Enhanced categorization with proper weighted scoring"""
        # Combine title and content, giving title more weight
        text = f"{title} {title} {content}".lower()
        
        ministry_scores = defaultdict(float)
        
        for ministry, priority_groups in MINISTRY_KEYWORDS.items():
            total_score = 0
            keyword_matches = []
            
            for priority_level, keywords in priority_groups.items():
                weight = PRIORITY_WEIGHTS[priority_level]
                
                for keyword in keywords:
                    keyword_lower = keyword.lower()
                    # Count occurrences of the keyword
                    count = text.count(keyword_lower)
                    
                    if count > 0:
                        score = count * weight
                        total_score += score
                        keyword_matches.append(f"{keyword}({count})")
            
            if total_score > 0:
                # Normalize score based on text length to avoid bias towards longer articles
                normalized_score = total_score / max(len(text.split()), 1) * 100
                ministry_scores[ministry] = normalized_score
                
                logger.debug(f"Ministry '{ministry}': score={total_score:.2f}, normalized={normalized_score:.2f}, matches={keyword_matches[:5]}")
        
        if ministry_scores:
            # Get the best scoring ministry
            best_ministry = max(ministry_scores, key=ministry_scores.get)
            best_score = ministry_scores[best_ministry]
            
            # Set minimum confidence threshold
            MIN_CONFIDENCE = 0.5
            
            if best_score >= MIN_CONFIDENCE:
                logger.info(f"Categorized as '{best_ministry}' with confidence {best_score:.2f}")
                return best_ministry, best_score
            else:
                logger.info(f"Low confidence categorization: '{best_ministry}' ({best_score:.2f}) < threshold ({MIN_CONFIDENCE})")
        
        return "general", 0.0

    def extract_content_advanced(self, soup, base_url):
        """Improved content extraction with better text cleaning"""
        articles = []
        
        # Multiple strategies for finding articles
        selectors = [
            # Generic article selectors
            'article',
            '[class*="story"]',
            '[class*="article"]',
            '[class*="news"]',
            '[class*="post"]',
            '[class*="item"]',
            # Header selectors
            'h1, h2, h3, h4',
            # Link selectors with meaningful text
            'a[title]',
            # Content containers
            '[class*="content"] h2',
            '[class*="content"] h3',
            # News specific
            '[class*="headline"]',
            '[class*="title"]'
        ]
        
        found_articles = set()
        
        for selector in selectors:
            try:
                elements = soup.select(selector)
                
                for element in elements[:30]:  # Limit to avoid too many elements
                    try:
                        # Extract title
                        title = ""
                        
                        if element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                            title = element.get_text(strip=True)
                        elif element.name == 'a' and element.get('title'):
                            title = element.get('title').strip()
                        elif element.name == 'article':
                            title_elem = element.find(['h1', 'h2', 'h3', 'h4', 'h5'])
                            if title_elem:
                                title = title_elem.get_text(strip=True)
                        else:
                            # Try to find title in the element
                            title_elem = element.find(['h1', 'h2', 'h3', 'h4', 'h5']) or element
                            title = title_elem.get_text(strip=True)
                        
                        # Clean and validate title
                        title = re.sub(r'\s+', ' ', title).strip()
                        title = re.sub(r'^[^a-zA-Z\u0900-\u097F\u0980-\u09FF\u0C80-\u0CFF]*', '', title)
                        
                        # Skip if title is too short, too long, or contains unwanted content
                        if (len(title) < 15 or len(title) > 200 or
                            any(skip in title.lower() for skip in 
                                ['advertisement', 'sponsored', 'live:', 'watch:', 'video:', 'photo:', 'gallery:', 'breaking:', 'update:']) or
                            title.lower().startswith(('http', 'www', 'click', 'see', 'view', 'more'))):
                            continue
                        
                        # Check for duplicates
                        title_hash = hashlib.md5(title.lower().encode('utf-8')).hexdigest()
                        if title_hash in found_articles:
                            continue
                        found_articles.add(title_hash)
                        
                        # Extract content/description
                        content = ""
                        parent = element.parent
                        
                        # Look for content in various ways
                        content_sources = []
                        
                        # Method 1: Look for description/summary in parent
                        if parent:
                            desc_elem = parent.find(['p', 'div', 'span'], 
                                class_=re.compile(r'(summary|excerpt|desc|intro|lead)', re.I))
                            if desc_elem:
                                content_sources.append(desc_elem.get_text(strip=True))
                        
                        # Method 2: Look for first paragraph after title
                        if element.name in ['h1', 'h2', 'h3', 'h4', 'h5']:
                            next_elem = element.find_next('p')
                            if next_elem:
                                content_sources.append(next_elem.get_text(strip=True))
                        
                        # Method 3: Look for content in article container
                        if element.name == 'article':
                            paragraphs = element.find_all('p')
                            if paragraphs:
                                content_sources.append(paragraphs[0].get_text(strip=True))
                        
                        # Method 4: Use element's own text if it's long enough
                        if len(title) < 100:  # Only for shorter titles
                            elem_text = element.get_text(strip=True)
                            if len(elem_text) > len(title) + 20:
                                remaining_text = elem_text.replace(title, '').strip()
                                if len(remaining_text) > 20:
                                    content_sources.append(remaining_text)
                        
                        # Select best content
                        for source_content in content_sources:
                            if len(source_content) >= 30 and source_content.lower() != title.lower():
                                content = source_content
                                break
                        
                        # Clean content
                        if content:
                            content = re.sub(r'\s+', ' ', content).strip()
                            # Remove title from content if it appears
                            if title.lower() in content.lower():
                                content = content.replace(title, '').strip()
                            # Truncate if too long
                            if len(content) > 400:
                                content = content[:400] + "..."
                        
                        # If no good content found, create a brief one from title
                        if not content or len(content) < 20:
                            content = f"{title[:100]}{'...' if len(title) > 100 else ''}"
                        
                        # Extract URL
                        article_url = base_url
                        link_elem = None
                        
                        if element.name == 'a':
                            link_elem = element
                        else:
                            # Look for link in or around the element
                            link_elem = (element.find('a', href=True) or 
                                       (element.parent and element.parent.find('a', href=True)) or
                                       element.find_previous('a', href=True) or
                                       element.find_next('a', href=True))
                        
                        if link_elem and link_elem.get('href'):
                            href = link_elem['href']
                            if href.startswith('http'):
                                article_url = href
                            elif href.startswith('/'):
                                article_url = urljoin(base_url, href)
                            elif href and not href.startswith('#'):
                                article_url = urljoin(base_url, href)
                        
                        articles.append({
                            'title': title,
                            'content': content,
                            'url': article_url
                        })
                        
                        # Limit to avoid too many articles per source
                        if len(articles) >= 15:
                            break
                            
                    except Exception as e:
                        logger.debug(f"Error processing element: {str(e)}")
                        continue
                
                # Break if we have enough articles
                if len(articles) >= 15:
                    break
                    
            except Exception as e:
                logger.debug(f"Error with selector {selector}: {str(e)}")
                continue
        
        # Remove duplicates and return best articles
        unique_articles = []
        seen_titles = set()
        
        for article in articles:
            title_normalized = re.sub(r'[^\w\s]', '', article['title'].lower())
            if title_normalized not in seen_titles and len(title_normalized) > 10:
                seen_titles.add(title_normalized)
                unique_articles.append(article)
        
        logger.info(f"Extracted {len(unique_articles)} unique articles from {len(articles)} total")
        return unique_articles[:10]  # Return top 10 per source

    def scrape_generic_news(self, url, source_name, language):
        """Enhanced generic scraping with better error handling and retry logic"""
        max_retries = 2
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Scraping {source_name} ({language}): {url} (attempt {attempt + 1})")
                
                # Add random delay to avoid rate limiting
                time.sleep(random.uniform(1, 3))
                
                # Randomize user agent for each request
                self.headers['User-Agent'] = random.choice([
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
                ])
                
                response = self.session.get(url, timeout=25, allow_redirects=True)
                response.raise_for_status()
                
                # Check if we got actual HTML content
                if 'text/html' not in response.headers.get('content-type', ''):
                    logger.warning(f"Non-HTML response from {url}")
                    continue
                
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Remove unwanted elements
                for unwanted in soup(['script', 'style', 'nav', 'header', 'footer', 
                                    'aside', 'iframe', 'noscript', 'form', 'button']):
                    unwanted.decompose()
                
                # Extract articles using advanced method
                article_data = self.extract_content_advanced(soup, url)
                
                if not article_data:
                    logger.warning(f"No articles found for {source_name}")
                    if attempt < max_retries - 1:
                        time.sleep(5)  # Wait before retry
                        continue
                    return []
                
                articles = []
                for data in article_data:
                    try:
                        # Categorize by ministry with confidence score
                        ministry, confidence = self.categorize_by_ministry(data['title'], data['content'])
                        
                        article = NewsArticle(
                            title=data['title'],
                            content=data['content'],
                            url=data['url'],
                            source=source_name,
                            timestamp=datetime.now().isoformat(),
                            ministry=ministry,
                            language=language,
                            confidence=confidence
                        )
                        
                        articles.append(article)
                        
                    except Exception as e:
                        logger.warning(f"Error creating article: {str(e)}")
                        continue
                
                logger.info(f"Successfully scraped {len(articles)} articles from {source_name}")
                return articles
                
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout scraping {url} (attempt {attempt + 1})")
                if attempt < max_retries - 1:
                    time.sleep(5)
                    continue
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 403:
                    logger.error(f"Access forbidden for {url} - skipping")
                    return []
                else:
                    logger.warning(f"HTTP error {e.response.status_code} for {url} (attempt {attempt + 1})")
                    if attempt < max_retries - 1:
                        time.sleep(5)
                        continue
            except Exception as e:
                logger.warning(f"Error scraping {url} (attempt {attempt + 1}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(5)
                    continue
        
        logger.error(f"Failed to scrape {url} after {max_retries} attempts")
        return []

    def scrape_news_by_language(self, language):
        """Scrape news from all sources for a specific language"""
        if language not in NEWS_SOURCES:
            logger.error(f"Language '{language}' not supported")
            return []
        
        all_articles = []
        sources = NEWS_SOURCES[language]
        
        for source in sources:
            try:
                articles = self.scrape_generic_news(source['url'], source['name'], language)
                all_articles.extend(articles)
                
                # Small delay between sources
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"Error scraping {source['name']}: {str(e)}")
                continue
        
        logger.info(f"Total articles scraped for {language}: {len(all_articles)}")
        return all_articles

    def get_news_by_ministry_and_language(self, ministry=None, language=None):
        """Get news filtered by ministry and language"""
        # Clear seen articles for fresh scraping
        self.seen_articles.clear()
        
        all_articles = []
        
        languages_to_scrape = [language] if language else list(NEWS_SOURCES.keys())
        
        for lang in languages_to_scrape:
            articles = self.scrape_news_by_language(lang)
            all_articles.extend(articles)
        
        # Filter by ministry if specified
        if ministry and ministry != 'all':
            filtered_articles = [a for a in all_articles if a.ministry == ministry]
            if filtered_articles:
                all_articles = filtered_articles
                logger.info(f"Found {len(filtered_articles)} articles for ministry: {ministry}")
            else:
                logger.warning(f"No articles found for ministry: {ministry}")
                # Return general articles as fallback
                general_articles = [a for a in all_articles if a.ministry == 'general']
                all_articles = general_articles[:5]
        
        # Sort by confidence score and timestamp
        all_articles.sort(key=lambda x: (x.confidence, x.timestamp), reverse=True)
        
        # Return appropriate number of articles
        limit = 8 if ministry else 20
        return all_articles[:limit]

# Initialize scraper
scraper = NewsScraper()

@app.route('/api/news', methods=['GET'])
def get_news():
    """Enhanced API endpoint with better filtering and statistics"""
    try:
        language = request.args.get('language', None)
        ministry = request.args.get('ministry', None)
        
        logger.info(f"API Request - Language: {language}, Ministry: {ministry}")
        
        articles = scraper.get_news_by_ministry_and_language(ministry, language)
        
        # Calculate statistics
        ministry_counts = defaultdict(int)
        language_counts = defaultdict(int)
        confidence_stats = []
        
        for article in articles:
            ministry_counts[article.ministry] += 1
            language_counts[article.language] += 1
            confidence_stats.append(article.confidence)
        
        # Calculate average confidence
        avg_confidence = sum(confidence_stats) / len(confidence_stats) if confidence_stats else 0
        
        response_data = {
            "articles": [article.to_dict() for article in articles],
            "total": len(articles),
            "statistics": {
                "ministry_distribution": dict(ministry_counts),
                "language_distribution": dict(language_counts),
                "average_confidence": round(avg_confidence, 2),
                "high_confidence_articles": len([c for c in confidence_stats if c > 2.0])
            },
            "filters": {
                "language": language,
                "ministry": ministry
            },
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"Returning {len(articles)} articles - Ministry dist: {dict(ministry_counts)} - Avg confidence: {avg_confidence:.2f}")
        return jsonify(response_data)
    
    except Exception as e:
        logger.error(f"Error in get_news endpoint: {str(e)}")
        return jsonify({
            "error": "Internal server error", 
            "message": str(e),
            "articles": [],
            "total": 0
        }), 500

@app.route('/api/languages', methods=['GET'])
def get_languages():
    """Get available languages"""
    return jsonify({
        "languages": list(NEWS_SOURCES.keys()),
        "total": len(NEWS_SOURCES)
    })

@app.route('/api/ministries', methods=['GET'])
def get_ministries():
    """Get available ministries with descriptions"""
    ministries_info = {}
    for ministry in MINISTRY_KEYWORDS.keys():
        ministries_info[ministry] = {
            "name": ministry.replace('_', ' ').title(),
            "keywords_count": sum(len(keywords) for keywords in MINISTRY_KEYWORDS[ministry].values())
        }
    
    ministries_info["general"] = {
        "name": "General",
        "keywords_count": 0
    }
    
    return jsonify({
        "ministries": ministries_info,
        "total": len(ministries_info)
    })

@app.route('/api/sources', methods=['GET'])
def get_sources():
    """Get all news sources"""
    return jsonify(NEWS_SOURCES)

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "4.0",
        "features": {
            "improved_categorization": True,
            "confidence_scoring": True,
            "better_content_extraction": True,
            "retry_mechanism": True
        },
        "sources_count": sum(len(sources) for sources in NEWS_SOURCES.values()),
        "ministries_count": len(MINISTRY_KEYWORDS) + 1,
        "total_keywords": sum(sum(len(keywords) for keywords in ministry.values()) 
                            for ministry in MINISTRY_KEYWORDS.values())
    })

if __name__ == '__main__':
    print("🚀 Starting Enhanced News Scraper Server v4.0...")
    print("📊 Available endpoints:")
    print("  • GET /api/news - Get all news")
    print("  • GET /api/news?language=bengali - Get Bengali news")
    print("  • GET /api/news?ministry=health - Get health ministry news")
    print("  • GET /api/news?language=hindi&ministry=finance - Get Hindi finance news")
    print("  • GET /api/languages - Get available languages")
    print("  • GET /api/ministries - Get available ministries")
    print("  • GET /api/sources - Get news sources")
    print("  • GET /api/health - Health check")
    print("🌐 Server running on http://localhost:5000")
    print("🔧 v4.0 Improvements:")
    print("  ✅ Comprehensive multilingual keyword system")
    print("  ✅ Weighted priority scoring for better accuracy")
    print("  ✅ Confidence scoring for each categorization")
    print("  ✅ Better content extraction with multiple strategies")
    print("  ✅ Retry mechanism for failed requests")
    print("  ✅ Enhanced duplicate detection")
    print("  ✅ Added Agriculture ministry category")
    app.run(debug=True, port=5000)