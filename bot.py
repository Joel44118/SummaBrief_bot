import os
import asyncio
import collections
import re
from aiohttp import web, ClientSession

# Fetch Environment Variables
TOKEN = os.getenv("TELEGRAM_TOKEN")
API_URL = f"https://api.telegram.org/bot{TOKEN}/"

# A basic list of English "stop words" to ignore when counting keyword frequencies
STOP_WORDS = set([
    "i", "me", "my", "myself", "we", "our", "ours", "ourselves", "you", "your", "yours", "he", "him", "his", 
    "she", "her", "it", "its", "they", "them", "their", "what", "which", "who", "whom", "this", "that", "am", 
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "having", "do", "does", "did", 
    "a", "an", "the", "and", "but", "if", "or", "because", "as", "until", "while", "of", "at", "by", "for", 
    "with", "about", "against", "between", "into", "through", "during", "before", "after", "above", "below", 
    "to", "from", "up", "down", "in", "out", "on", "off", "over", "under", "again", "further", "then", "once"
])

# 1. Pure Python Sentence Splitter (Replaces NLTK punkt)
def split_into_sentences(text):
    # Splits text by periods, exclamation marks, or question marks followed by spaces and capital letters
    sentences = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?)\s', text)
    return [s.strip() for s in sentences if s.strip()]

# 2. Pure Python Extractive Summarizer Logic
def summarize_text(text, max_sentences=3):
    # Clean formatting
    text = re.sub(r'\s+', ' ', text)
    
    # Split text into sentences cleanly using regex
    sentences = split_into_sentences(text)
    
    # If the text is already short, return it as is
    if len(sentences) <= max_sentences:
        return text

    # Tokenize words manually using regex to strip punctuation
    words = re.findall(r'\b\w+\b', text.lower())
    
    word_frequencies = collections.Counter(
        word for word in words if word not in STOP_WORDS
    )
    
    # Normalize frequencies
    max_freq = max(word_frequencies.values(), default=1)
    for word in word_frequencies:
        word_frequencies[word] /= max_freq

    # Score sentences based on the keywords they contain
    sentence_scores = {}
    for sentence in sentences:
        sentence_words = re.findall(r'\b\w+\b', sentence.lower())
        for word in sentence_words:
            if word in word_frequencies:
                if sentence not in sentence_scores:
                    sentence_scores[sentence] = word_frequencies[word]
                else:
                    sentence_scores[sentence] += word_frequencies[word]

    # Select the highest-scoring sentences
    summarized_sentences = sorted(
        sentence_scores, key=sentence_scores.get, reverse=True
    )[:max_sentences]
    
    # Re-order the summary sentences so they match the original text flow
    summary = " ".join([sent for sent in sentences if sent in summarized_sentences])
    return summary

# 3. Web Server Route (Health Check for Railway)
async def handle_health(request):
    return web.Response(text="SummaBrief Summarizer is active!")

# 4. Main Bot Long Polling Loop
async def bot_polling():
    offset = 0
    print("SummaBrief polling started...")
    
    async with ClientSession() as session:
        while True:
            try:
                url = f"{API_URL}getUpdates"
                params = {"offset": offset, "timeout": 30}
                
                async with session.get(url, params=params, timeout=35) as response:
                    res_json = await response.json()
                    
                    if res_json.get("ok") and res_json.get("result"):
                        for update in res_json["result"]:
                            offset = update["update_id"] + 1
                            message = update.get("message", {})
                            chat_id = message.get("chat", {}).get("id")
                            text = message.get("text", "").strip()
                            
                            if not chat_id or not text:
                                continue
                                
                            if text == "/start":
                                reply_text = "📄 **Welcome to SummaBrief!**\n\nPaste or forward any long text block/article here, and I will instantly extract the core summary for you."
                            else:
                                # Run the text summarizer safely
                                try:
                                    summary = summarize_text(text)
                                    reply_text = f"📝 **Summary:**\n\n_{summary}_"
                                except Exception as nlp_err:
                                    print(f"Core Summarizer Error: {nlp_err}")
                                    reply_text = "❌ Sorry, I had trouble parsing that specific layout of text. Try sending it in plain paragraphs."
                                
                            # Send response
                            send_url = f"{API_URL}sendMessage"
                            payload = {"chat_id": chat_id, "text": reply_text, "parse_mode": "Markdown"}
                            await session.post(send_url, data=payload)
                                
            except Exception as e:
                print(f"Polling error: {e}")
                await asyncio.sleep(5)

# 5. Application Launcher
async def main():
    app = web.Application()
    app.router.add_get('/', handle_health)
    
    port = int(os.getenv("PORT", 8080))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    
    await site.start()
    await bot_polling()

if __name__ == "__main__":
    asyncio.run(main())
