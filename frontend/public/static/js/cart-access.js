(function() {
    const pendingKey = "ramjicart_pending_cart_add";

    function csrfToken() {
        const cookie = document.cookie.split("; ")
            .find(function(value) { return value.startsWith("csrftoken="); });
        return cookie
            ? decodeURIComponent(cookie.split("=").slice(1).join("="))
            : "";
    }

    function currentPage() {
        return window.location.pathname + window.location.search + window.location.hash;
    }

    function sendGuestToLogin(payload) {
        const returnTo = currentPage();
        try {
            sessionStorage.setItem(pendingKey, JSON.stringify({ returnTo: returnTo, payload: payload }));
        } catch (error) {
            console.error("Could not save the pending cart item:", error);
        }
        window.location.href = "/login.html?cart=1&next=" + encodeURIComponent(returnTo);
    }

    async function postCartItem(payload) {
        const response = await fetch("/api/customer/cart", {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken()
            },
            body: JSON.stringify(payload)
        });
        const data = await response.json();
        if (!response.ok) {
            const error = new Error(data.message || "Could not add item to cart.");
            error.status = response.status;
            throw error;
        }
        return data;
    }

    async function add(payload) {
        const response = await window.RamjicartAuth.currentUser();
        if (response.status === 401) {
            sendGuestToLogin(payload);
            return null;
        }
        if (!response.ok) throw new Error("Could not check your login status.");
        const account = await response.json();
        if (account.role !== "customer") throw new Error("A customer account is required to add items to the cart.");
        try {
            return await postCartItem(payload);
        } catch (error) {
            if (error.status === 401) {
                sendGuestToLogin(payload);
                return null;
            }
            throw error;
        }
    }

    async function resumePendingAdd() {
        let pending;
        try {
            pending = JSON.parse(sessionStorage.getItem(pendingKey) || "null");
        } catch (error) {
            console.error("Could not read the pending cart item:", error);
            try { sessionStorage.removeItem(pendingKey); } catch (_storageError) {}
            return;
        }
        if (!pending || pending.returnTo !== currentPage() || !pending.payload) return;
        try { sessionStorage.removeItem(pendingKey); } catch (_storageError) {}
        try {
            const data = await postCartItem(pending.payload);
            document.dispatchEvent(new CustomEvent("ramjicart:pending-cart-result", {
                detail: { success: true, data: data, payload: pending.payload }
            }));
        } catch (error) {
            console.error("Could not add the pending cart item:", error);
            document.dispatchEvent(new CustomEvent("ramjicart:pending-cart-result", {
                detail: { success: false, error: error, payload: pending.payload }
            }));
        }
    }

    window.RamjicartCartAccess = Object.freeze({
        add: add,
        resumePendingAdd: resumePendingAdd
    });
})();
