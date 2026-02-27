import requests
import json

API_URL = "https://eswopm4jm1.execute-api.ap-south-1.amazonaws.com/default/google-summarizer"

def summarize_text(text, max_words_per_chunk=400):
    payload = {
        "text": text,
        "max_words_per_chunk": max_words_per_chunk
    }
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(API_URL, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        data = response.json()
        return data.get("summary", "")
    except requests.exceptions.RequestException as e:
        print(f"Error calling Lambda API: {e}")
        if e.response is not None:
            print(e.response.text)
        return None
    
    
def summarize_text_from_pdf(pdf_file, max_words_per_chunk=400):
    webhook_url = "https://n8n.orravyn.cloud/webhook/05c364cf-2cdb-4675-8bd0-0993aba6d70f"

    try:
        files = {"file": ("document.pdf", pdf_file, "application/pdf")}
        response = requests.post(webhook_url, files=files)
        response.raise_for_status()

        return response.text.strip()
    
    except requests.exceptions.RequestException as e:
        print(f"Error calling webhook: {e}")
        if hasattr(e, "response") and e.response is not None:
            print(e.response.text)
        return "Error generating summary."
    
    except Exception as e:
        print(f"Unexpected error: {e}")
        return "Error processing PDF file."


if __name__ == "__main__":
    TEXT = """
    Coronavirus disease 2019 (COVID-19) is a contagious disease caused by the coronavirus SARS-CoV-2.
    In January 2020, the disease spread worldwide, resulting in the COVID-19 pandemic.
    """
    
    summary = summarize_text(TEXT)
    print("Summary:\n", summary)
