const btn = document.getElementById("url-submit");
const copyBtn = document.getElementById("copy");
const finalText = document.getElementById("res-link");

async function createShortLink() {
  copyBtn.innerHTML = "";
  finalText.innerHTML = `<span>Creating link...</span>`;
  const data = await fetch("/create", {
    method: "POST",
    referrer: document.domain,
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      link: document.getElementById("url-input").value,
    }),
  }).then((res) => res.json());

  if (data.id) {
    finalText.innerHTML = `<a href="https://${document.domain}${document.location.port ? `:${document.location.port}` : ''}/${data.id}">https://${document.domain}${document.location.port ? `:${document.location.port}` : ''}/${data.id}</a> `;
    copyBtn.innerHTML = `<button>📋</button>`;
  } else finalText.innerHTML = `<span>${data.error}</span>`;
  return;
}

btn.addEventListener("click", async function (event) {
  event.preventDefault();
  await createShortLink();
});

copyBtn.addEventListener("click", async function (event) {
  event.preventDefault();
  navigator.clipboard.writeText(finalText.textContent);
});
