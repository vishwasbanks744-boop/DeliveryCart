(function() {
    const style = document.createElement("style");
    style.textContent = `
        .product-gallery-dialog { width:min(920px,calc(100% - 28px)); max-width:920px; padding:18px; border:0; border-radius:18px; background:#fff; color:#20252b; box-shadow:0 18px 60px #1115; }
        .product-gallery-dialog::backdrop { background:#1119; }
        .product-gallery-head { display:flex; align-items:center; justify-content:space-between; gap:12px; margin-bottom:12px; }
        .product-gallery-title { min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-weight:700; }
        .product-gallery-close,.product-gallery-arrow { display:grid; place-items:center; width:40px; height:40px; border:0; border-radius:50%; background:#fff0eb; color:#d8432c; font-size:22px; cursor:pointer; }
        .product-gallery-frame { position:relative; overflow:hidden; border-radius:14px; background:#151515; }
        .product-gallery-track { display:flex; overflow-x:auto; scroll-snap-type:x mandatory; scrollbar-width:none; overscroll-behavior-x:contain; }
        .product-gallery-track::-webkit-scrollbar { display:none; }
        .product-gallery-track img { flex:0 0 100%; width:100%; height:min(68vh,640px); object-fit:contain; scroll-snap-align:center; }
        .product-gallery-count { position:absolute; top:12px; right:12px; padding:6px 10px; border-radius:20px; background:#111b; color:#fff; font-size:13px; }
        .product-gallery-controls { display:flex; align-items:center; justify-content:center; gap:12px; margin-top:12px; }
        .product-gallery-dots { display:flex; align-items:center; justify-content:center; gap:7px; }
        .product-gallery-dot { width:8px; height:8px; padding:0; border:0; border-radius:8px; background:#c9cdd3; cursor:pointer; transition:width .18s,background .18s; }
        .product-gallery-dot.is-active { width:23px; background:#f04b32; }
        @media(max-width:600px) { .product-gallery-dialog { padding:12px; } .product-gallery-track img { height:62vh; } }
    `;
    document.head.appendChild(style);

    let dialog;
    function getDialog() {
        if (dialog) return dialog;
        dialog = document.createElement("dialog");
        dialog.className = "product-gallery-dialog";
        dialog.innerHTML = `
            <div class="product-gallery-head"><strong class="product-gallery-title"></strong><button class="product-gallery-close" type="button" aria-label="Close photo viewer">×</button></div>
            <div class="product-gallery-frame"><div class="product-gallery-track"></div><span class="product-gallery-count"></span></div>
            <div class="product-gallery-controls"><button type="button" class="product-gallery-arrow" data-step="-1" aria-label="Previous photo">‹</button><div class="product-gallery-dots"></div><button type="button" class="product-gallery-arrow" data-step="1" aria-label="Next photo">›</button></div>`;
        document.body.appendChild(dialog);
        dialog.querySelector(".product-gallery-close").addEventListener("click", () => dialog.close());
        dialog.addEventListener("click", event => { if (event.target === dialog) dialog.close(); });
        return dialog;
    }

    function open(images, title) {
        const sources = (images || []).map(item => typeof item === "string" ? item : item && item.url).filter(Boolean);
        if (!sources.length) return;
        const view = getDialog();
        const track = view.querySelector(".product-gallery-track");
        const dots = view.querySelector(".product-gallery-dots");
        const count = view.querySelector(".product-gallery-count");
        view.querySelector(".product-gallery-title").textContent = title || "Product photos";
        track.replaceChildren();
        dots.replaceChildren();
        sources.forEach((src, index) => {
            const image = document.createElement("img");
            image.src = src;
            image.alt = (title || "Product") + " photo " + (index + 1);
            track.appendChild(image);
            if (sources.length > 1) {
                const dot = document.createElement("button");
                dot.type = "button";
                dot.className = "product-gallery-dot" + (index === 0 ? " is-active" : "");
                dot.setAttribute("aria-label", "Show photo " + (index + 1));
                dot.addEventListener("click", () => image.scrollIntoView({behavior:"smooth", inline:"center", block:"nearest"}));
                dots.appendChild(dot);
            }
        });
        count.hidden = sources.length < 2;
        dots.parentElement.hidden = sources.length < 2;
        const arrows = Array.from(view.querySelectorAll(".product-gallery-arrow"));
        arrows.forEach(button => {
            button.hidden = sources.length < 2;
            button.onclick = () => {
                const current = Math.round(track.scrollLeft / track.clientWidth);
                const next = Math.max(0, Math.min(sources.length - 1, current + Number(button.dataset.step)));
                track.children[next].scrollIntoView({behavior:"smooth", inline:"center", block:"nearest"});
            };
        });
        let scrollFrame = 0;
        track.onscroll = () => {
            cancelAnimationFrame(scrollFrame);
            scrollFrame = requestAnimationFrame(() => {
                const current = Math.max(0, Math.min(sources.length - 1, Math.round(track.scrollLeft / track.clientWidth)));
                count.textContent = `${current + 1} / ${sources.length}`;
                dots.querySelectorAll("button").forEach((dot, index) => dot.classList.toggle("is-active", index === current));
            });
        };
        count.textContent = `1 / ${sources.length}`;
        track.scrollLeft = 0;
        if (!view.open) view.showModal();
    }

    window.RamjicartProductGallery = {open};
})();
