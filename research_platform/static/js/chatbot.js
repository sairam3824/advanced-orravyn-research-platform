// Platform Help Chatbot - Knowledge Base and Logic

// Knowledge Base with Q&A patterns
const knowledgeBase = [
    // Paper Management
    {
        keywords: ['upload', 'submit', 'add paper', 'publish paper'],
        answer: "📄 To upload a paper:\n1. Click 'Papers' in the navigation menu\n2. Click 'Upload Paper'\n3. Fill in the title, abstract, authors, and upload PDF\n4. Submit for moderator approval\n\nNote: Papers need approval before being published.",
        links: [{ text: 'Upload Paper', url: '/papers/upload/' }]
    },
    {
        keywords: ['bookmark', 'save paper', 'favorite'],
        answer: "🔖 Your bookmarks are saved papers you want to read later!\n\nTo bookmark a paper:\n• Click the bookmark icon on any paper\n• View all bookmarks from your profile menu\n• Organize bookmarks into folders",
        links: [{ text: 'View Bookmarks', url: '/papers/bookmarks/' }]
    },
    {
        keywords: ['edit paper', 'modify paper', 'update paper'],
        answer: "✏️ To edit your paper:\n1. Go to 'My Papers' from your profile menu\n2. Click the edit icon on your paper\n3. Make your changes\n4. Save\n\nNote: Only your own papers can be edited.",
        links: [{ text: 'My Papers', url: '/papers/my-papers/' }]
    },
    {
        keywords: ['delete paper', 'remove paper'],
        answer: "🗑️ To delete a paper:\n1. Go to 'My Papers'\n2. Click the delete icon\n3. Confirm deletion\n\nWarning: This action cannot be undone!",
        links: [{ text: 'My Papers', url: '/papers/my-papers/' }]
    },
    {
        keywords: ['reading list', 'paper list', 'collection'],
        answer: "📚 Reading Lists help you organize papers!\n\nYou can:\n• Create custom reading lists\n• Add papers to lists\n• Share lists with others\n• Make lists public or private",
        links: [{ text: 'My Reading Lists', url: '/papers/reading-lists/' }]
    },
    
    // Groups & Collaboration
    {
        keywords: ['group', 'join group', 'create group', 'research group'],
        answer: "👥 Research Groups let you collaborate!\n\nTo join a group:\n1. Go to 'Groups' in the menu\n2. Browse available groups\n3. Click 'Join Group'\n\nTo create a group:\n1. Go to 'Groups'\n2. Click 'Create Group'\n3. Fill in details and invite members",
        links: [
            { text: 'Browse Groups', url: '/groups/' },
            { text: 'My Groups', url: '/groups/my-groups/' }
        ]
    },
    {
        keywords: ['collaboration', 'collaborate', 'work together'],
        answer: "🤝 Collaboration features:\n\n• Join research groups\n• Create research projects\n• Share reading lists\n• Message other researchers\n• Co-author papers\n\nView your collaboration network in your dashboard!",
        links: [{ text: 'Collaboration Network', url: '/analytics/network/' }]
    },
    {
        keywords: ['message', 'chat', 'dm', 'direct message'],
        answer: "💬 To message other researchers:\n1. Click your profile menu\n2. Select 'Messages'\n3. Start a new conversation\n4. Select a user and send your message",
        links: [{ text: 'Messages', url: '/messaging/conversations/' }]
    },
    
    // Navigation & Features
    {
        keywords: ['dashboard', 'home', 'main page'],
        answer: "📊 Your Dashboard shows:\n• Recent papers you've read\n• Your bookmarks\n• Reading statistics\n• Recommendations\n• Activity feed",
        links: [{ text: 'Go to Dashboard', url: '/accounts/dashboard/' }]
    },
    {
        keywords: ['profile', 'account', 'settings'],
        answer: "👤 Your Profile includes:\n• Personal information\n• Research interests\n• Uploaded papers\n• Statistics\n• ORCID integration\n\nEdit your profile from the profile menu!",
        links: [{ text: 'View Profile', url: '/accounts/profile/' }]
    },
    {
        keywords: ['notification', 'alert', 'updates'],
        answer: "🔔 Notifications keep you updated!\n\nYou'll receive notifications for:\n• Comments on your papers\n• New ratings\n• Paper approvals\n• New followers\n• Group invitations\n• Messages",
        links: [{ text: 'View Notifications', url: '/messaging/notifications/' }]
    },
    {
        keywords: ['search', 'find paper', 'look for'],
        answer: "🔍 To search for papers:\n1. Click 'Search' in the menu\n2. Enter keywords, authors, or topics\n3. Use filters for categories, year, citations\n4. Enable boolean search for advanced queries (AND, OR, NOT)",
        links: [{ text: 'Search Papers', url: '/search/' }]
    },
    {
        keywords: ['category', 'categories', 'topics'],
        answer: "🏷️ Categories help organize papers by topic!\n\n• Browse papers by category\n• Request new categories\n• Filter search by category\n• See trending topics",
        links: [{ text: 'Browse Categories', url: '/papers/categories/' }]
    },
    
    // Yggdrasil & AI
    {
        keywords: ['yggdrasil', 'ai', 'chatbot', 'research assistant'],
        answer: "🌳 Yggdrasil is our AI Research Assistant!\n\nUse it for:\n• Research questions\n• Paper summaries\n• Literature reviews\n• Academic discussions\n• Research recommendations\n\nNote: I help with platform features, Yggdrasil helps with research!",
        links: [{ text: 'Open Yggdrasil', url: '/chat/yggdrasil_chatbot/' }]
    },
    
    // Blog & Publishing
    {
        keywords: ['blog', 'write post', 'article'],
        answer: "📝 Research Blog lets you share insights!\n\nTo write a post:\n1. Go to 'Blog' in the menu\n2. Click 'Write Post'\n3. Write your content\n4. Submit for approval\n\nPosts are reviewed by moderators before publishing.",
        links: [{ text: 'View Blog', url: '/papers/blog/' }]
    },
    {
        keywords: ['publisher', 'researchers', 'authors'],
        answer: "👨‍🔬 Publishers are researchers who share papers!\n\n• Browse all publishers\n• Follow publishers\n• See their papers\n• View their profiles\n• Check their H-index",
        links: [{ text: 'Browse Publishers', url: '/accounts/publishers/' }]
    },
    
    // Analytics & Stats
    {
        keywords: ['analytics', 'statistics', 'stats', 'metrics'],
        answer: "📈 Analytics Dashboard shows:\n• Reading statistics\n• Paper impact metrics\n• Collaboration network\n• Trending topics\n• Research field analytics",
        links: [{ text: 'Research Dashboard', url: '/analytics/dashboard/' }]
    },
    {
        keywords: ['trending', 'popular', 'hot topics'],
        answer: "🔥 Trending Topics shows:\n• Most viewed papers\n• Popular research areas\n• Growing fields\n• Weekly trends\n• Category-based trends",
        links: [{ text: 'View Trending', url: '/analytics/trending/' }]
    },
    
    // Account & Access
    {
        keywords: ['login', 'sign in', 'access'],
        answer: "🔐 To access your account:\n1. Click 'Login' in the top right\n2. Enter your email and password\n3. Click 'Sign In'\n\nForgot password? Use the reset link on the login page.",
        links: [{ text: 'Login', url: '/accounts/login/' }]
    },
    {
        keywords: ['register', 'sign up', 'create account'],
        answer: "✨ To create an account:\n1. Click 'Register' in the top right\n2. Fill in your details\n3. Choose your user type (Student/Researcher/Publisher)\n4. Submit\n\nYou'll be able to access all platform features!",
        links: [{ text: 'Register', url: '/accounts/register/' }]
    },
    
    // Help & Support
    {
        keywords: ['help', 'support', 'assistance', 'how to'],
        answer: "🆘 I'm here to help!\n\nAsk me about:\n• Uploading papers\n• Using features\n• Navigation\n• Groups & collaboration\n• Your account\n• Any platform feature\n\nFor research questions, use Yggdrasil!",
        links: []
    },
    {
        keywords: ['share', 'sharing', 'social media'],
        answer: "🔗 To share papers:\n1. Open any paper\n2. Click the 'Share' button\n3. Choose platform:\n   • Twitter\n   • LinkedIn\n   • Facebook\n   • Email\n   • Copy Link\n\nShares are tracked in your analytics!",
        links: []
    },
    {
        keywords: ['like', 'upvote', 'favorite paper'],
        answer: "❤️ To like a paper:\n• Click the heart icon on any paper\n• View liked papers in your profile\n• See total likes on papers\n\nLikes help show paper popularity!",
        links: []
    }
];

// Default responses
const defaultResponses = [
    "I'm not sure about that. Could you rephrase your question?",
    "Hmm, I don't have information on that. Try asking about papers, groups, or platform features!",
    "I didn't quite understand. Ask me about uploading papers, bookmarks, groups, or other features!",
];

// Toggle chatbot window
function toggleChatbot() {
    const chatWindow = document.getElementById('chatWindow');
    const toggle = document.getElementById('chatbotToggle');
    
    if (chatWindow.classList.contains('active')) {
        chatWindow.classList.remove('active');
        toggle.innerHTML = '<i class="fas fa-question-circle"></i>';
    } else {
        chatWindow.classList.add('active');
        toggle.innerHTML = '<i class="fas fa-times"></i>';
        document.getElementById('chatInput').focus();
    }
}

// Handle enter key in input
function handleChatKeypress(event) {
    if (event.key === 'Enter') {
        sendMessage();
    }
}

// Send quick reply
function sendQuickReply(message) {
    document.getElementById('chatInput').value = message;
    sendMessage();
}

// Send message
function sendMessage() {
    const input = document.getElementById('chatInput');
    const message = input.value.trim();
    
    if (!message) return;
    
    // Add user message
    addMessage(message, 'user');
    input.value = '';
    
    // Show typing indicator
    showTypingIndicator();
    
    // Get bot response after delay
    setTimeout(() => {
        hideTypingIndicator();
        const response = getBotResponse(message);
        addMessage(response.answer, 'bot', response.links);
    }, 800);
}

// Add message to chat
function addMessage(text, sender, links = []) {
    const messagesDiv = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `${sender}-message`;
    
    let linksHTML = '';
    if (links && links.length > 0) {
        linksHTML = '<div class="quick-replies" style="margin-top: 0.75rem;">';
        links.forEach(link => {
            linksHTML += `<button onclick="window.location.href='${link.url}'">${link.text} →</button>`;
        });
        linksHTML += '</div>';
    }
    
    messageDiv.innerHTML = `
        <div class="message-avatar">
            <i class="fas fa-${sender === 'bot' ? 'robot' : 'user'}"></i>
        </div>
        <div class="message-content">
            <p>${text.replace(/\n/g, '<br>')}</p>
            ${linksHTML}
        </div>
    `;
    
    messagesDiv.appendChild(messageDiv);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

// Show typing indicator
function showTypingIndicator() {
    const messagesDiv = document.getElementById('chatMessages');
    const typingDiv = document.createElement('div');
    typingDiv.className = 'bot-message';
    typingDiv.id = 'typingIndicator';
    typingDiv.innerHTML = `
        <div class="message-avatar">
            <i class="fas fa-robot"></i>
        </div>
        <div class="typing-indicator">
            <span></span>
            <span></span>
            <span></span>
        </div>
    `;
    messagesDiv.appendChild(typingDiv);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

// Hide typing indicator
function hideTypingIndicator() {
    const indicator = document.getElementById('typingIndicator');
    if (indicator) {
        indicator.remove();
    }
}

// Get bot response using pattern matching
function getBotResponse(message) {
    const lowerMessage = message.toLowerCase();
    
    // Search knowledge base
    for (const item of knowledgeBase) {
        for (const keyword of item.keywords) {
            if (lowerMessage.includes(keyword.toLowerCase())) {
                return {
                    answer: item.answer,
                    links: item.links || []
                };
            }
        }
    }
    
    // Default response if no match
    const randomDefault = defaultResponses[Math.floor(Math.random() * defaultResponses.length)];
    return {
        answer: randomDefault + "\n\nTry asking:\n• How do I upload a paper?\n• Where are my bookmarks?\n• What is Yggdrasil?\n• How do I join a group?",
        links: []
    };
}
