import os
import json
import re
import time
import logging
import urllib.request
import urllib.error

try:
    import boto3
except Exception:
    boto3 = None

logger = logging.getLogger()
logger.setLevel(logging.INFO)

HF_MODEL = os.environ.get("HF_MODEL", "facebook/bart-large-cnn")
HF_API_TOKEN = os.environ.get("HF_API_TOKEN")
HF_SECRET_ARN = os.environ.get("HF_SECRET_ARN")

MAX_WORDS_PER_CHUNK = int(os.environ.get("MAX_WORDS_PER_CHUNK", "700"))
MAX_CHUNKS = int(os.environ.get("MAX_CHUNKS", "30"))
HF_MAX_RETRIES = int(os.environ.get("HF_MAX_RETRIES", "4"))
HF_REQUEST_TIMEOUT = int(os.environ.get("HF_REQUEST_TIMEOUT", "60"))

HF_MIN_LENGTH = int(os.environ.get("HF_MIN_LENGTH", "150"))
HF_MAX_LENGTH = int(os.environ.get("HF_MAX_LENGTH", "600"))
HF_LENGTH_PENALTY = float(os.environ.get("HF_LENGTH_PENALTY", "2.0"))

FINAL_MIN_LENGTH = int(os.environ.get("FINAL_MIN_LENGTH", "250"))
FINAL_MAX_LENGTH = int(os.environ.get("FINAL_MAX_LENGTH", "350"))

ENV_DEBUG = str(os.environ.get("DEBUG", "false")).lower() in ("1", "true", "yes")


# ---------- Helpers ----------
def get_token_from_secrets_manager(secret_arn):
    if not boto3:
        raise RuntimeError("boto3 not available to read Secrets Manager")
    client = boto3.client("secretsmanager")
    resp = client.get_secret_value(SecretId=secret_arn)
    secret_str = resp.get("SecretString")
    if not secret_str:
        raise RuntimeError("SecretString empty in Secrets Manager response")
    try:
        d = json.loads(secret_str)
        return d.get("HF_API_TOKEN") or d.get("hf_api_token") or d.get("token") or None
    except Exception:
        return secret_str


def get_hf_token():
    if HF_API_TOKEN:
        return HF_API_TOKEN
    if HF_SECRET_ARN:
        token = get_token_from_secrets_manager(HF_SECRET_ARN)
        if token:
            return token
    raise RuntimeError("Hugging Face token not found. Set HF_API_TOKEN or HF_SECRET_ARN.")


def split_into_sentences(text):
    text = text.strip()
    if not text:
        return []
    return re.split(r'(?<=[.!?])\s+', text)


def chunk_sentences_by_wordcount(sentences, max_words):
    chunks, cur, cur_words = [], [], 0
    for s in sentences:
        wcount = len(s.split())
        if wcount > max_words:
            if cur:
                chunks.append(" ".join(cur))
                cur, cur_words = [], 0
            words = s.split()
            for i in range(0, len(words), max_words):
                chunks.append(" ".join(words[i:i+max_words]))
            continue
        if cur_words + wcount <= max_words:
            cur.append(s)
            cur_words += wcount
        else:
            chunks.append(" ".join(cur))
            cur, cur_words = [s], wcount
    if cur:
        chunks.append(" ".join(cur))
    return chunks


def hf_inference_call(text, token, model=HF_MODEL,
                      timeout=HF_REQUEST_TIMEOUT, retries=HF_MAX_RETRIES,
                      min_length=HF_MIN_LENGTH, max_length=HF_MAX_LENGTH,
                      length_penalty=HF_LENGTH_PENALTY,
                      wait_for_model=False):
    url = f"https://api-inference.huggingface.co/models/{model}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {
        "inputs": text,
        "parameters": {
            "min_length": int(min_length),
            "max_length": int(max_length),
            "length_penalty": float(length_penalty)
        }
    }
    if wait_for_model:
        payload["options"] = {"wait_for_model": True}

    data = json.dumps(payload).encode("utf-8")
    attempt, last_err = 0, None

    while attempt < retries:
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                resp_body = resp.read().decode("utf-8")
                try:
                    result = json.loads(resp_body)
                except Exception:
                    return resp_body

                if isinstance(result, dict) and result.get("error"):
                    err = result.get("error")
                    if any(tok in err.lower() for tok in ("loading", "unavailable", "timeout", "429")):
                        attempt += 1
                        time.sleep(1 * (2 ** attempt))
                        last_err = err
                        continue
                    raise RuntimeError(f"HuggingFace inference error: {err}")

                if isinstance(result, list) and len(result) > 0:
                    first = result[0]
                    if isinstance(first, dict):
                        return first.get("summary_text") or first.get("generated_text") or str(first)
                    return str(first)

                return str(result)

        except urllib.error.HTTPError as e:
            try:
                body = e.read().decode()
            except Exception:
                body = "<no body>"
            if e.code in (429, 503, 502):
                attempt += 1
                time.sleep(1 * (2 ** attempt))
                last_err = f"HTTPError {e.code}: {body}"
                continue
            raise RuntimeError(f"HF HTTPError {e.code}: {body}")
        except Exception as ex:
            attempt += 1
            last_err = str(ex)
            time.sleep(1 * (2 ** attempt))

    raise RuntimeError(f"Exceeded retries calling HF API. Last error: {last_err}")


# ---------- Lambda handler ----------
def lambda_handler(event, context):
    try:
        body_raw = event.get("body") or ""
        body = json.loads(body_raw) if isinstance(body_raw, str) and body_raw else body_raw
    except Exception as e:
        return {"statusCode": 400, "body": json.dumps({"error": "invalid JSON body", "detail": str(e)})}

    text = body.get("text") or body.get("input") or ""
    if not text:
        return {"statusCode": 400, "body": json.dumps({"error": "missing 'text' in request body"})}

    max_words = int(body.get("max_words_per_chunk", MAX_WORDS_PER_CHUNK))

    try:
        token = get_hf_token()
    except Exception as e:
        return {"statusCode": 500, "body": json.dumps({"error": "HF token missing", "detail": str(e)})}

    sentences = split_into_sentences(text)
    chunks = chunk_sentences_by_wordcount(sentences, max_words)

    if len(chunks) > MAX_CHUNKS:
        msg = f"Input too large: produced {len(chunks)} chunks (max {MAX_CHUNKS})."
        return {"statusCode": 413, "body": json.dumps({"error": msg, "chunks": len(chunks)})}

    chunk_summaries = []
    for i, c in enumerate(chunks, start=1):
        try:
            s = hf_inference_call(
                c, token,
                min_length=HF_MIN_LENGTH,
                max_length=HF_MAX_LENGTH,
                length_penalty=HF_LENGTH_PENALTY
            )
            chunk_summaries.append(s)
        except Exception as ex:
            return {"statusCode": 502, "body": json.dumps({"error": f"failed summarizing chunk {i}", "detail": str(ex)})}

    combined_summary = " ".join(chunk_summaries)

    try:
        final_summary = hf_inference_call(
            combined_summary, token,
            min_length=FINAL_MIN_LENGTH,
            max_length=FINAL_MAX_LENGTH,
            length_penalty=1.5
        )
    except Exception as ex:
        return {"statusCode": 502, "body": json.dumps({"error": "failed final summarization", "detail": str(ex)})}

    response = {
        "summary": final_summary,
        "chunks": len(chunks),
        "chunk_summaries_count": len(chunk_summaries),
    }
    return {"statusCode": 200, "body": json.dumps(response)}