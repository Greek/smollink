const btn = document.getElementById("url-submit");
const copyBtn = document.getElementById("copy");
const finalText = document.getElementById("res-link");

async function createShortLink() {
  copyBtn.innerHTML = "";
  finalText.innerHTML = `Creating link...`;
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
    finalText.innerHTML = `<a href="https://${document.domain}/${data.id}">https://${document.domain}/${data.id}</a> `;
    copyBtn.innerHTML = `<button
    class="w-auto p-[.6em] mt-2 bg-[#181818] font-mono hover:bg-[#242424] focus-visible:outline-none">
    📋
</button>`;
  } else finalText.innerHTML = `${data.error}`;
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
