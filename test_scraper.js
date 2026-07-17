const BASE_URL = "https://www.mdsuexam.org/";
const TARGET_VCNT_URL = "https://www.mdsuexam.org/vcnt.php";
const TARGET_FORMACTION_URL = "https://www.mdsuexam.org/FormActIon.php";
const TARGET_STUDENT_URL = "https://www.mdsuexam.org/StudentmaINpanel.php";

async function translateToHindi(text) {
  if (!text) return "";
  try {
    const url = `https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=hi&dt=t&q=${encodeURIComponent(text)}`;
    const res = await fetch(url);
    const data = await res.json();
    return data[0].map(s => s[0]).join("");
  } catch (err) {
    console.error("Translation failed:", err.message);
    return text;
  }
}

async function run() {
  console.log("Step 1: Fetching vcnt.php...");
  const headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.mdsuexam.org/"
  };

  const res1 = await fetch(TARGET_VCNT_URL, { headers });
  const html1 = await res1.text();

  const cookieHeader = res1.headers.get("set-cookie");
  if (cookieHeader) {
    headers["Cookie"] = cookieHeader.split(';')[0];
  }

  // Extract form inputs from vcnt.php
  const inputRegex = /<input\s+type="hidden"\s+name="([^"]+)"\s+id="[^"]*"\s+value="([^"]*)"/gi;
  let match;
  const formData1 = new URLSearchParams();
  while ((match = inputRegex.exec(html1)) !== null) {
    formData1.append(match[1], match[2]);
  }
  if (html1.includes('id="sbt"')) {
    formData1.append("sbt", "Wait..");
  }

  // Find form action
  const formActionRegex = /<form[^>]+action="([^"]+)"/i;
  const formActionMatch = formActionRegex.exec(html1);
  const action1 = formActionMatch ? formActionMatch[1] : "MdSmaINpanel.php";
  const actionUrl1 = new URL(action1, BASE_URL).toString();

  console.log("Step 2: Submitting POST redirect to MdSmaINpanel.php...");
  const res2 = await fetch(actionUrl1, {
    method: "POST",
    headers: { ...headers, "Content-Type": "application/x-www-form-urlencoded" },
    body: formData1.toString()
  });
  const html2 = await res2.text();

  if (html2.includes("Security Code does not matched")) {
    throw new Error("Security verification failed at MdSmaINpanel.php.");
  }

  // Parse notifications from MdSmaINpanel.php
  console.log("Parsing general notifications...");
  const aRegex = /<a\s+[^>]*href=['"](PDF\/[^'"]+\.pdf)['"][^>]*>([\s\S]*?)<\/a>/gi;
  const notifications = [];
  while ((match = aRegex.exec(html2)) !== null) {
    const href = match[1].trim();
    let title = match[2].replace(/<[^>]*>/g, '').trim();
    title = title.replace(/\s+/g, ' ');
    if (!title) title = href.split('/').pop();
    notifications.push({ id: href, title, url: new URL(href, BASE_URL).toString() });
  }

  // Parse inputs from MdSmaINpanel.php to POST to FormActIon.php
  const formRegex = /<form[^>]+name="f1"[^>]*>([\s\S]*?)<\/form>/i;
  const formMatch = formRegex.exec(html2);
  const formData2 = new URLSearchParams();
  if (formMatch) {
    const formInner = formMatch[1];
    const inputRegex2 = /<input\s+[^>]*name="([^"]+)"[^>]*value="([^"]*)"/gi;
    let match2;
    while ((match2 = inputRegex2.exec(formInner)) !== null) {
      formData2.append(match2[1], match2[2]);
    }
  }
  formData2.set("flag", "1");

  console.log("Step 3: Redirecting through FormActIon.php...");
  const res3 = await fetch(TARGET_FORMACTION_URL, {
    method: "POST",
    headers: { ...headers, "Content-Type": "application/x-www-form-urlencoded", "Referer": actionUrl1 },
    body: formData2.toString()
  });
  const html3 = await res3.text();

  // Parse inputs from FormActIon.php response to POST to StudentmaINpanel.php
  const formMatch3 = formRegex.exec(html3);
  const formData3 = new URLSearchParams();
  if (formMatch3) {
    const formInner3 = formMatch3[1];
    const inputRegex3 = /<input\s+[^>]*name="([^"]+)"[^>]*value="([^"]*)"/gi;
    let match3;
    while ((match3 = inputRegex3.exec(formInner3)) !== null) {
      formData3.append(match3[1], match3[2]);
    }
  } else {
    const inputRegex3 = /<input\s+[^>]*name="([^"]+)"[^>]*value="([^"]*)"/gi;
    let match3;
    while ((match3 = inputRegex3.exec(html3)) !== null) {
      formData3.append(match3[1], match3[2]);
    }
  }

  console.log("Step 4: Submitting final POST to StudentmaINpanel.php...");
  const res4 = await fetch(TARGET_STUDENT_URL, {
    method: "POST",
    headers: { ...headers, "Content-Type": "application/x-www-form-urlencoded", "Referer": TARGET_FORMACTION_URL },
    body: formData3.toString()
  });
  let html4 = await res4.text();

  if (html4.includes("Security Code does not matched")) {
    throw new Error("Security verification failed at StudentmaINpanel.php.");
  }

  console.log("Cleaning broken HTML row tags...");
  // Replace the broken developer markup: <tr><tr or </tr><tr> or <tr>\s*<tr
  html4 = html4.replace(/<tr>\s*<tr/gi, "</tr><tr");
  html4 = html4.replace(/<\/td>\s*<tr>\s*<tr/gi, "</td></tr><tr");

  console.log("Parsing courses from student panel...");
  // Now retry regex match on cleaned HTML
  const trRegex = /<tr\s+[^>]*bgcolor=['"](#BBD9F7|#D9EAFB)['"][^>]*>([\s\S]*?)<\/tr>/gi;
  const courses = [];
  let trMatch;
  while ((trMatch = trRegex.exec(html4)) !== null) {
    const trInner = trMatch[2];
    const tdRegex = /<td[^>]*>([\s\S]*?)<\/td>/gi;
    const tds = [];
    let tdMatch;
    while ((tdMatch = tdRegex.exec(trInner)) !== null) {
      tds.push(tdMatch[1]);
    }

    if (tds.length >= 5) {
      let rawName = tds[0].replace(/<[^>]*>/g, '').trim();
      let name = rawName.includes(':') ? rawName.split(':')[1].trim() : rawName;
      name = name.replace("(REVISED)", "").trim();

      // Check if time table exists
      const ttMatch = /href=['"](PDF\/[^'"]+\.pdf)['"]/i.exec(tds[1]);
      const timeTable = ttMatch ? ttMatch[1] : "";

      // Check if admit card exists
      const hasAdmitCard = tds[2].includes("Download Admit Card");

      // Check if result exists
      const hasResult = tds[4].includes("View Result");

      courses.push({
        name,
        timeTable,
        hasAdmitCard,
        hasResult
      });
    }
  }

  console.log("--------------------------------------------------");
  console.log(`✅ Success! Parsed ${notifications.length} general notifications & ${courses.length} courses.`);
  console.log("--------------------------------------------------");

  // Test translation and formatting for top items
  console.log("\n--- TEST PREVIEW: LATEST NOTIFICATION (HINDI TRANSLATED) ---");
  if (notifications.length > 0) {
    const testNotif = notifications[3]; // Skip helper pins
    console.log(`English Title: ${testNotif.title}`);
    const hindiTitle = await translateToHindi(testNotif.title);
    const sampleMsg = buildMsg(hindiTitle, "https://mdsuplus.com/sample-post-slug/", testNotif.url);
    console.log(sampleMsg);
  }

  console.log("\n--- TEST PREVIEW: COURSE RESULT RELEASE (HINDI TRANSLATED) ---");
  // Find a course that has result released, or use first course
  const resultCourse = courses.find(c => c.hasResult) || courses[1];
  if (resultCourse) {
    console.log(`English Course: ${resultCourse.name}`);
    const hindiCourse = await translateToHindi(resultCourse.name);
    const sampleResultMsg = buildMsg(`एमडीएसयू ${hindiCourse} का रिजल्ट जारी कर दिया गया है।`, "https://mdsuplus.com/sample-result-slug/", "https://www.mdsuexam.org/");
    console.log(sampleResultMsg);
  }
  console.log("--------------------------------------------------");
}

function buildMsg(statusText, wpLink, directLink) {
  return `*MDSU Latest Update*

${statusText}

👇👇👇👇👇👇👇👇

🔗 *Read Update:* ${wpLink}
📥 *Direct Link:* ${directLink}

👉सबसे पहले लेटेस्ट अपडेट पाने के लिए हमारे व्हाट्सएप एवं टेलीग्राम चैनल को जरूर फॉलो करें 👈

*👇👇👇Join Now👇👇👇*

*Join Whatsapp Channel*

https://whatsapp.com/channel/0029Vb87pC44Y9liEfVCsK1Q

*Join Telegram Channel*

https://t.me/mdsuplus1`;
}

run().catch(err => console.error("❌ Test failed:", err));
