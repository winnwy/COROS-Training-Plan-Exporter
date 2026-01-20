// 1. Go to the COROS training plan page
// 2. Open Developer Tools (F12 or Right Click -> Inspect)
// 3. Go to the "Console" tab
// 4. Paste this entire script and press Enter
// 5. The training data will be copied to your clipboard!

const container = document.querySelector('.table-body') || document.body;
const text = container.innerText;

// Copy to clipboard
const textArea = document.createElement("textarea");
textArea.value = text;
document.body.appendChild(textArea);
textArea.select();
document.execCommand("Copy");
textArea.remove();

console.log("✅ Training data copied to clipboard!");

