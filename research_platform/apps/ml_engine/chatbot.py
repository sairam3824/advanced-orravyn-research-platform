class ResearchChatBot:
    def __init__(self):
        pass
    
    def generate_response(self, message, paper):
        """Generate a simple bot response"""
        message_lower = message.lower()
        
        if 'abstract' in message_lower:
            return f"The abstract of this paper is: {paper.abstract[:200]}..."
        elif 'author' in message_lower:
            return f"The authors of this paper are: {paper.authors}"
        elif 'date' in message_lower or 'year' in message_lower:
            return f"This paper was published on: {paper.publication_date}"
        elif 'category' in message_lower or 'topic' in message_lower:
            categories = ", ".join([cat.name for cat in paper.categories.all()])
            return f"This paper belongs to the following categories: {categories}"
        else:
            return "I'm a research assistant bot. You can ask me about the paper's abstract, authors, publication date, or categories."
