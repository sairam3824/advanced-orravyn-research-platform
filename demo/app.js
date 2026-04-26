const users = {
  admin: {
    name: "Admin User",
    role: "admin",
    email: "admin@orravyn.demo",
    password: "demo1234",
    copy: "Full platform access: users, papers, moderation, analytics and AI."
  },
  moderator: {
    name: "Moderator User",
    role: "moderator",
    email: "moderator@orravyn.demo",
    password: "demo1234",
    copy: "Moderation-focused access: approval queues, categories, papers and AI review."
  },
  publisher: {
    name: "Publisher User",
    role: "publisher",
    email: "publisher@orravyn.demo",
    password: "demo1234",
    copy: "Publisher access: upload papers, track impact, write blog posts and join groups."
  },
  reader: {
    name: "Reader User",
    role: "reader",
    email: "reader@orravyn.demo",
    password: "demo1234",
    copy: "Reader access: search papers, bookmark, read summaries and ask Yggdrasil."
  }
};

const papers = [
  ["Hierarchical Adaptive Retrieval for Scientific Assistants", "S. Maruri, A. Rao", "Computer Science", "Approved", "Dense retrieval, BM25, reciprocal rank fusion, reranking and citation verification for scientific RAG."],
  ["Discourse-Aware Section-Hierarchical Summarization", "R. Iyer, M. Chen", "Machine Learning", "Pending", "Section-aware summaries with methodology and results weighting for long-form papers."],
  ["Multi-Agent Research Orchestration with Evidence Debate", "V. Patel, L. Kumar", "AI Systems", "Approved", "Planner, retrieval, critic, synthesizer and memory agents coordinate a grounded research workflow."],
  ["Cold-Start Recommendation in Collaborative Research Groups", "N. Shah, P. Lee", "Recommender Systems", "Approved", "Group-guided paper suggestions for users without ratings or bookmarks."]
];

const categories = [
  ["Computer Science", "52 approved papers", "RAG, retrieval, graph systems and NLP."],
  ["Machine Learning", "39 approved papers", "Models, training, evaluation and benchmarks."],
  ["Medicine", "16 approved papers", "Biomedical evidence, PubMed summaries and clinical NLP."],
  ["Engineering", "18 approved papers", "Systems papers, optimization and deployment."],
  ["Social Sciences", "11 approved papers", "Human evaluation and collaboration behavior."],
  ["Physics", "12 approved papers", "Scientific workflows and computational methods."]
];

const publishers = [
  ["Sai Ram Maruri", "VIT Andhra Pradesh", "28", "410", "Verified"],
  ["Aarav Rao", "Graph Analytics Lab", "17", "210", "Verified"],
  ["Meera Chen", "Open Research Group", "14", "156", "Pending"],
  ["Vikram Patel", "AI Safety Methods", "11", "98", "Verified"]
];

const groups = [
  ["Graph Analytics Lab", "Private group", "18 members", "34 papers"],
  ["Scientific NLP Review", "Public group", "41 members", "72 papers"],
  ["AI Safety Methods", "Private group", "12 members", "21 papers"],
  ["Biomedical Summarization", "Public group", "27 members", "48 papers"]
];

const posts = [
  ["How HA-RAG improves scientific search", "Published", "A short explanation of hybrid retrieval in Orravyn."],
  ["Building faithful paper summaries", "Pending", "Human evaluation, ROUGE and BERTScore workflows."],
  ["Using groups for cold-start recommendations", "Published", "How group papers influence static and live recommendations."]
];

let currentUser = users.admin;
let isAuthenticated = false;
let pendingRoute = "dashboard";

const loginView = document.querySelector("#loginView");
const appView = document.querySelector("#appView");
const loginForm = document.querySelector("#loginForm");
const emailInput = document.querySelector("#email");
const passwordInput = document.querySelector("#password");
const demoNotice = document.querySelector("#demoNotice");
const demoNoticeClose = document.querySelector("#demoNoticeClose");
const loginButton = document.querySelector("#loginButton");
const routeButtons = document.querySelectorAll("[data-route]");
const routes = document.querySelectorAll(".route");
const drawer = document.querySelector("#accountDrawer");

function card(title, meta, body) {
  return `<article class="mini-card"><h3>${title}</h3><p>${body}</p><div class="paper-meta"><span>${meta}</span></div></article>`;
}

function paperRow(item, compact = false) {
  const statusClass = item[3] === "Pending" ? "pending" : "status";
  return `
    <article class="paper-row">
      <div>
        <h3>${item[0]}</h3>
        <p>${item[4]}</p>
        <div class="paper-meta">
          <span>${item[1]}</span><span>${item[2]}</span><span class="${statusClass}">${item[3]}</span>
        </div>
      </div>
      ${compact ? "" : `<div class="row-actions"><button>View</button><button>Bookmark</button></div>`}
    </article>
  `;
}

function renderStaticData() {
  document.querySelector("#paperList").innerHTML = papers.map((paper) => paperRow(paper)).join("");
  document.querySelector("#searchResults").innerHTML = papers.slice(0, 3).map((paper) => paperRow(paper, true)).join("");
  document.querySelector("#categoryGrid").innerHTML = categories.map((cat) => card(cat[0], cat[1], cat[2])).join("");
  document.querySelector("#groupGrid").innerHTML = groups.map((group) => card(group[0], `${group[1]} · ${group[2]}`, `${group[3]} in shared collections.`)).join("");
  document.querySelector("#blogGrid").innerHTML = posts.map((post) => card(post[0], post[1], post[2])).join("");
  document.querySelector("#publisherRows").innerHTML = publishers.map((row) => `<tr>${row.map((cell) => `<td>${cell}</td>`).join("")}</tr>`).join("");
  document.querySelector("#moderationRows").innerHTML = [
    ["Discourse-Aware Section-Hierarchical Summarization", "Publisher User", "Paper", "Pending", "Approve"],
    ["Biomedical Summarization", "Meera Chen", "Category", "Pending", "Review"],
    ["Building faithful paper summaries", "Publisher User", "Blog", "Pending", "Approve"]
  ].map((row) => `<tr>${row.map((cell, index) => `<td>${index === 4 ? `<button class="secondary">${cell}</button>` : cell}</td>`).join("")}</tr>`).join("");
}

function setUser(userKey) {
  currentUser = users[userKey] || users.admin;
  emailInput.value = currentUser.email;
  passwordInput.value = currentUser.password;
}

function applyRole() {
  document.querySelector("#accountButton").textContent = currentUser.name;
  document.querySelector("#roleBadge").textContent = currentUser.role[0].toUpperCase() + currentUser.role.slice(1);
  document.querySelector("#drawerName").textContent = currentUser.name;
  document.querySelector("#drawerRole").textContent = `${currentUser.role} account`;
  document.querySelector("#chatUserLabel").textContent = currentUser.name;

  document.querySelectorAll("[class*='role-']").forEach((element) => {
    const allowed = Array.from(element.classList).some((cls) => cls === `role-${currentUser.role}`);
    element.classList.toggle("role-hidden", !allowed);
  });

  const metrics = currentUser.role === "reader"
    ? [["Bookmarks", "18"], ["Reading lists", "4"], ["AI questions", "27"], ["Groups joined", "3"]]
    : [["Uploaded papers", "28"], ["Total views", "12.8k"], ["Downloads", "1,942"], ["Impact score", "91"]];
  document.querySelector("#metrics").innerHTML = metrics.map((metric) => `<article class="metric"><span>${metric[0]}</span><strong>${metric[1]}</strong></article>`).join("");
  document.querySelector("#dashboardTitle").textContent = `${currentUser.role[0].toUpperCase() + currentUser.role.slice(1)} dashboard`;
  document.querySelector("#dashboardMetrics").innerHTML = metrics.map((metric) => `<article class="metric"><span>${metric[0]}</span><strong>${metric[1]}</strong></article>`).join("");

  const activityByRole = {
    admin: ["Reviewed platform health and user counts.", "Checked 36 pending moderation items.", "Opened the global analytics dashboard."],
    moderator: ["Approved a retrieval paper.", "Reviewed a new category request.", "Checked flagged blog comments."],
    publisher: ["Uploaded a paper draft.", "Opened paper impact analytics.", "Created a research blog post."],
    reader: ["Bookmarked HA-SciRAG.", "Updated reading progress.", "Asked Yggdrasil a comparison question."]
  };
  document.querySelector("#activityList").innerHTML = activityByRole[currentUser.role].map((item) => `<li>${item}</li>`).join("");
  document.querySelector("#dashboardRecommendations").innerHTML = papers.slice(0, 2).map((paper) => paperRow(paper, true)).join("");
}

function setSessionMode(authenticated) {
  isAuthenticated = authenticated;
  appView.classList.toggle("public-mode", !authenticated);
  drawer.classList.add("hidden");
}

function showLogin(returnRoute = "dashboard") {
  pendingRoute = returnRoute === "home" ? "dashboard" : returnRoute;
  appView.classList.add("hidden");
  loginView.classList.remove("hidden");
  drawer.classList.add("hidden");
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function showRoute(routeName) {
  if (routeName !== "home" && !isAuthenticated) {
    showLogin(routeName);
    return;
  }

  const resolved = routeName === "home" ? "home" : routeName;
  loginView.classList.add("hidden");
  appView.classList.remove("hidden");
  routes.forEach((route) => route.classList.toggle("active", route.dataset.page === resolved));
  document.querySelectorAll(".nav-links [data-route]").forEach((button) => {
    button.classList.toggle("active", button.dataset.route === routeName);
  });
  drawer.classList.add("hidden");
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function dismissDemoNotice() {
  if (demoNotice.classList.contains("hidden")) return;
  demoNotice.classList.add("hidden");
  showRoute("home");
}

document.querySelectorAll(".quick-users button").forEach((button) => {
  button.addEventListener("click", () => setUser(button.dataset.user));
});

demoNoticeClose.addEventListener("click", dismissDemoNotice);

setTimeout(dismissDemoNotice, 5500);

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    dismissDemoNotice();
  }
});

loginButton.addEventListener("click", () => showLogin("dashboard"));

loginForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const matched = Object.entries(users).find(([, user]) => user.email === emailInput.value.trim());
  currentUser = matched ? matched[1] : currentUser;
  setSessionMode(true);
  loginView.classList.add("hidden");
  appView.classList.remove("hidden");
  applyRole();
  showRoute(pendingRoute);
});

routeButtons.forEach((button) => {
  button.addEventListener("click", (event) => {
    event.preventDefault();
    if (button.dataset.route) showRoute(button.dataset.route);
  });
});

document.querySelector("#accountButton").addEventListener("click", () => drawer.classList.toggle("hidden"));
document.querySelector("#logoutButton").addEventListener("click", () => {
  setSessionMode(false);
  pendingRoute = "dashboard";
  showRoute("home");
});

document.querySelector("#chatForm").addEventListener("submit", (event) => {
  event.preventDefault();
  const input = document.querySelector("#chatInput");
  const text = input.value.trim();
  if (!text) return;
  const messages = document.querySelector("#chatMessages");
  messages.insertAdjacentHTML("beforeend", `
    <div class="chat-message user"><strong>${currentUser.name}</strong><p>${text}</p></div>
    <div class="chat-message bot"><strong>Yggdrasil</strong><p>Static demo response: Orravyn routes this through planner, platform retrieval, web/arXiv expansion, critic filtering and synthesis with source badges.</p></div>
  `);
  input.value = "Show recommendation reasons for this user";
});

document.querySelector("#hero-search-form").addEventListener("submit", (event) => {
  event.preventDefault();
  showRoute("search");
});

document.querySelector("#hero-search-input").addEventListener("input", (event) => {
  const query = event.target.value.trim();
  const dropdown = document.querySelector("#hero-search-dropdown");
  if (!query) {
    dropdown.classList.remove("open");
    dropdown.innerHTML = "";
    return;
  }
  dropdown.innerHTML = papers.slice(0, 3).map((paper) => `
    <a href="#" data-route="papers" class="hsd-item">
      <div class="hsd-icon"><i class="fas fa-file-alt"></i></div>
      <div>
        <div class="hsd-title">${paper[0]}</div>
        <div class="hsd-meta">${paper[1].split(",")[0]} · ${paper[2]}</div>
      </div>
    </a>
  `).join("") + `<div class="hsd-footer">View all results for "${query}" <i class="fas fa-arrow-right"></i></div>`;
  dropdown.classList.add("open");
  dropdown.querySelectorAll("[data-route]").forEach((item) => {
    item.addEventListener("click", (clickEvent) => {
      clickEvent.preventDefault();
      showRoute(item.dataset.route);
    });
  });
});

renderStaticData();
applyRole();
setSessionMode(false);
showRoute("home");
