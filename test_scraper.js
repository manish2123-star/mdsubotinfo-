const fs = require('fs');
const path = require('path');

const TARGET_VCNT_URL = "https://mdsuexam.org/vcnt.php";
const BASE_URL = "https://mdsuexam.org/";

async function fetchAndParseMDSU() {
  console.log("Step 1: Fetching vcnt.php...");
  const headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://mdsuexam.org/"
  };

  const res1 = await fetch(TARGET_VCNT_URL, { headers });
  const html1 = await res1.text();

  const cookieHeader = res1.headers.get("set-cookie");
  if (cookieHeader) {
    headers["Cookie"] = cookieHeader.split(';')[0];
  }

  // Extract form inputs
  const inputRegex = /<input\s+type="hidden"\s+name="([^"]+)"\s+id="[^"]*"\s+value="([^"]*)"/gi;
  let match;
  const formData = new URLSearchParams();

  while ((match = inputRegex.exec(html1)) !== null) {
    formData.append(match[1], match[2]);
  }

  if (html1.includes('id="sbt"')) {
    formData.append("sbt", "Wait..");
  }

  // Find form action
  const formActionRegex = /<form[^>]+action="([^"]+)"/i;
  const formActionMatch = formActionRegex.exec(html1);
  const action = formActionMatch ? formActionMatch[1] : "MdSmaINpanel.php";
  const actionUrl = new URL(action, BASE_URL).toString();

  console.log("Step 2: Submitting POST redirect request...");
  const res2 = await fetch(actionUrl, {
    method: "POST",
    headers: {
      ...headers,
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: formData.toString()
  });

  const html2 = await res2.text();

  if (html2.includes("Security Code does not matched")) {
    throw new Error("Security verification failed.");
  }

  console.log("Step 3: Scraping updates from panel...");
  
  // Regex to extract <a href='PDF/...'><b>...</b></a> or similar
  // Matching href containing "PDF/" and ending with ".pdf"
  const aRegex = /<a\s+[^>]*href=['"](PDF\/[^'"]+\.pdf)['"][^>]*>([\s\S]*?)<\/a>/gi;
  const notifications = [];
  
  while ((match = aRegex.exec(html2)) !== null) {
    const href = match[1].trim();
    let title = match[2].replace(/<[^>]*>/g, '').trim(); // strip inner tags like <b>
    title = title.replace(/\s+/g, ' '); // collapse spaces
    
    if (!title) {
      title = href.split('/').pop();
    }
    
    notifications.append = notifications.push({
      id: href,
      title: title,
      url: new URL(href, BASE_URL).toString()
    });
  }

  return notifications;
}

async function run() {
  try {
    const notifications = await fetchAndParseMDSU();
    console.log("--------------------------------------------------");
    console.log(`✅ Web scraping was successful! Found ${notifications.length} notifications.`);
    console.log("\nTop 5 Latest Notifications:");
    
    notifications.slice(0, 5).forEach((notif, i) => {
      console.log(`\n[${i + 1}] ID: ${notif.id}`);
      console.log(`    Title: ${notif.title}`);
      console.log(`    URL: ${notif.url}`);
    });
    console.log("--------------------------------------------------");
  } catch (err) {
    console.error("❌ Scraping failed:", err);
  }
}

run();
