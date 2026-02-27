import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from peft import PeftModel
import logging
from typing import List, Optional
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BARTSummarizer:
    """BART-based summarizer using fine-tuned LoRA model."""
    
    def __init__(self, model_path: str, base_model: str = "facebook/bart-base"):
        """
        Initialize the summarizer with fine-tuned model.
        
        Args:
            model_path: Path to the fine-tuned LoRA model
            base_model: Base BART model name
        """
        self.device = self._get_device()
        self.model_path = model_path
        self.base_model = base_model
        
        logger.info(f"Loading model from {model_path}")
        logger.info(f"Using device: {self.device}")
        
        self.tokenizer = AutoTokenizer.from_pretrained(base_model)
        self.model = self._load_model()
        
    def _get_device(self):
        if torch.backends.mps.is_available() and torch.backends.mps.is_built():
            return torch.device("mps")
        if torch.cuda.is_available():
            return torch.device("cuda")
        return torch.device("cpu")
    
    def _load_model(self):
        try:
            base_model = AutoModelForSeq2SeqLM.from_pretrained(self.base_model)
            
            model = PeftModel.from_pretrained(base_model, self.model_path)
            model = model.to(self.device)
            model.eval()
            
            logger.info("Model loaded successfully")
            return model
            
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise
    
    def summarize_text(self, text: str, max_length: int = 256, min_length: int = 50, 
                      num_beams: int = 4, length_penalty: float = 2.0) -> str:
        """
        Summarize a single text passage.
        
        Args:
            text: Input text to summarize
            max_length: Maximum length of summary
            min_length: Minimum length of summary
            num_beams: Number of beams for beam search
            length_penalty: Length penalty for generation
            
        Returns:
            Generated summary
        """
        try:
            inputs = self.tokenizer(
                text,
                max_length=1024,
                truncation=True,
                padding=True,
                return_tensors="pt"
            ).to(self.device)
            
            with torch.no_grad():
                summary_ids = self.model.generate(
                    inputs["input_ids"],
                    attention_mask=inputs["attention_mask"],
                    max_length=max_length,
                    min_length=min_length,
                    num_beams=num_beams,
                    length_penalty=length_penalty,
                    early_stopping=True,
                    do_sample=False
                )
            
            summary = self.tokenizer.decode(
                summary_ids[0], 
                skip_special_tokens=True,
                clean_up_tokenization_spaces=True
            )
            
            return summary.strip()
            
        except Exception as e:
            logger.error(f"Summarization failed: {e}")
            return f"Error generating summary: {str(e)}"
    
    def summarize_chunks(self, text_chunks: List[str], **kwargs) -> List[str]:
        """
        Summarize multiple text chunks.
        
        Args:
            text_chunks: List of text chunks to summarize
            **kwargs: Additional arguments for summarize_text
            
        Returns:
            List of summaries for each chunk
        """
        summaries = []
        
        for i, chunk in enumerate(text_chunks):
            logger.info(f"Summarizing chunk {i+1}/{len(text_chunks)}")
            summary = self.summarize_text(chunk, **kwargs)
            summaries.append(summary)
        
        return summaries
    
    def hierarchical_summarize(self, text_chunks: List[str], 
                             chunk_max_length: int = 128,
                             final_max_length: int = 256) -> str:
        """
        Perform hierarchical summarization: summarize chunks, then summarize summaries.
        
        Args:
            text_chunks: List of text chunks
            chunk_max_length: Max length for individual chunk summaries
            final_max_length: Max length for final summary
            
        Returns:
            Final hierarchical summary
        """
        if not text_chunks:
            return "No content to summarize."
        
        if len(text_chunks) == 1:
            return self.summarize_text(text_chunks[0], max_length=final_max_length)
        
        logger.info("Step 1: Summarizing individual chunks")
        chunk_summaries = self.summarize_chunks(
            text_chunks, 
            max_length=chunk_max_length,
            min_length=20
        )
        
        logger.info("Step 2: Creating final summary")
        combined_summaries = " ".join(chunk_summaries)
        
        if len(combined_summaries) > 1000:
            from pdf_extractor import PDFExtractor
            extractor = PDFExtractor()
            summary_chunks = extractor.chunk_text(combined_summaries, max_length=800)
            
            if len(summary_chunks) > 1:
                return self.hierarchical_summarize(
                    summary_chunks, 
                    chunk_max_length=chunk_max_length,
                    final_max_length=final_max_length
                )
        
        final_summary = self.summarize_text(
            combined_summaries, 
            max_length=final_max_length,
            min_length=50
        )
        
        return final_summary
    
def summarize_text_from_pdf(pdf_file, max_words_per_chunk=400):
    """
    Summarize text from a PDF file.
    
    Args:
        pdf_file: Path to the PDF file
        max_words_per_chunk: Maximum words per chunk for processing
        
    Returns:
        Summary of the PDF content
    """
    try:
        from pdf_extractor import PDFExtractor
        
        logger.info(f"Processing PDF file: {pdf_file}")
        
        extractor = PDFExtractor()
        text_chunks = extractor.extract_and_chunk(pdf_file, max_words=max_words_per_chunk)
        
        if not text_chunks:
            return "No text content found in the PDF file."
        
        logger.info(f"Extracted {len(text_chunks)} chunks from PDF")
        
        summarizer = BARTSummarizer("./outputs_lora")
        
        summary = summarizer.hierarchical_summarize(text_chunks)
        
        return summary
        
    except Exception as e:
        logger.error(f"PDF summarization failed: {e}")
        return f"Error processing PDF: {str(e)}"


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python bart_summarizer.py <pdf_file>")
        sys.exit(1)
    
    pdf_file = sys.argv[1]
    
    if not os.path.exists(pdf_file):
        print(f"Error: PDF file '{pdf_file}' not found.")
        sys.exit(1)
    
    print(f"Summarizing PDF: {pdf_file}")
    summary = summarize_text_from_pdf(pdf_file)
    
    print("\n" + "="*50)
    print("SUMMARY")
    print("="*50)
    print(summary)
    print("="*50)