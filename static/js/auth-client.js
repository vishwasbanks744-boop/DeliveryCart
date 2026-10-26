(function() {
    let configPromise;
    let firebasePromise;
    let firebaseAuth;
    let firebaseMethods;

    function csrfToken() {
        const cookie = document.cookie.split("; ")
            .find(function(value) { return value.startsWith("csrftoken="); });
        return cookie
            ? decodeURIComponent(cookie.split("=").slice(1).join("="))
            : "";
    }

    function request(path, method, payload) {
        const options = { method: method, credentials: "same-origin" };
        const headers = {};
        if (method !== "GET") headers["X-CSRFToken"] = csrfToken();
        if (payload !== undefined) {
            headers["Content-Type"] = "application/json";
            options.body = JSON.stringify(payload);
        }
        options.headers = headers;
        return fetch(path, options);
    }

    function clientConfig() {
        if (!configPromise) {
            configPromise = fetch("/api/config/public", { credentials: "same-origin" })
                .then(function(response) {
                    if (!response.ok) throw new Error("Could not load sign-in configuration.");
                    return response.json();
                });
        }
        return configPromise;
    }

    async function getFirebase() {
        if (!firebasePromise) {
            firebasePromise = clientConfig().then(async function(config) {
                if (!config.firebaseEnabled || !config.firebase) {
                    throw new Error("Firebase sign-in is not enabled.");
                }
                const version = encodeURIComponent(config.firebaseSdkVersion || "13.1.0");
                const appSdk = await import(
                    "https://www.gstatic.com/firebasejs/" + version + "/firebase-app.js"
                );
                const authSdk = await import(
                    "https://www.gstatic.com/firebasejs/" + version + "/firebase-auth.js"
                );
                const app = appSdk.getApps().length
                    ? appSdk.getApp()
                    : appSdk.initializeApp(config.firebase);
                firebaseAuth = authSdk.getAuth(app);
                firebaseMethods = authSdk;
                return firebaseAuth;
            }).catch(function(error) {
                firebasePromise = null;
                throw error;
            });
        }
        await firebasePromise;
        return { auth: firebaseAuth, methods: firebaseMethods };
    }

    async function firebaseRegistration(profile, endpoint, email, password, displayName) {
        const firebase = await getFirebase();
        let credential;
        try {
            credential = await firebase.methods.createUserWithEmailAndPassword(
                firebase.auth, email, password
            );
        } catch (error) {
            if (error.code !== "auth/email-already-in-use") throw error;
            credential = await firebase.methods.signInWithEmailAndPassword(
                firebase.auth, email, password
            );
        }
        if (displayName && !credential.user.displayName) {
            await firebase.methods.updateProfile(credential.user, { displayName: displayName });
        }
        if (!credential.user.emailVerified) {
            await firebase.methods.sendEmailVerification(credential.user);
        }
        const payload = Object.assign({}, profile, {
            email: email,
            firebaseIdToken: await credential.user.getIdToken()
        });
        // The backend stores the verified Firebase UID and role profile; it never needs the password.
        delete payload.password;
        const response = await request(endpoint, "POST", payload);
        const result = await response.clone().json().catch(function() { return {}; });
        if (response.ok) {
            await firebase.methods.signOut(firebase.auth);
            result.message = (result.message || "Account created.")
                + " Check your email and verify it before signing in.";
        } else {
            // Keep the Firebase identity so the user can retry registration after fixing the reported issue.
            result.message = (result.message || "Registration failed.")
                + " If this email already has a profile, verify it and sign in with the same email to link your account.";
            return new Response(JSON.stringify(result), {
                status: response.status,
                headers: { "Content-Type": "application/json" }
            });
        }
        return new Response(JSON.stringify(result), {
            status: response.status,
            headers: { "Content-Type": "application/json" }
        });
    }

    async function login(credentials) {
        const config = await clientConfig();
        if (!config.firebaseEnabled) return request("/api/auth/login", "POST", credentials);
        const firebase = await getFirebase();
        const credential = await firebase.methods.signInWithEmailAndPassword(
            firebase.auth,
            String(credentials.email || "").trim(),
            String(credentials.password || "")
        );
        const response = await request("/api/auth/login", "POST", {
            firebaseIdToken: await credential.user.getIdToken(true),
            expectedRole: credentials.expectedRole || ""
        });
        if (!response.ok) await firebase.methods.signOut(firebase.auth);
        return response;
    }

    async function startGoogleSignIn() {
        const firebase = await getFirebase();
        const provider = new firebase.methods.GoogleAuthProvider();
        provider.setCustomParameters({ prompt: "select_account" });
        const credential = await firebase.methods.signInWithPopup(firebase.auth, provider);
        return {
            email: credential.user.email || "",
            displayName: credential.user.displayName || "",
            firebaseIdToken: await credential.user.getIdToken(true)
        };
    }

    async function loginWithGoogle(expectedRole) {
        const identity = await startGoogleSignIn();
        const response = await request("/api/auth/login", "POST", {
            firebaseIdToken: identity.firebaseIdToken,
            expectedRole: expectedRole || ""
        });
        if (!response.ok) {
            const firebase = await getFirebase();
            await firebase.methods.signOut(firebase.auth);
        }
        return response;
    }

    async function registerWithGoogle(endpoint, profile, identity) {
        if (!identity || !identity.firebaseIdToken) {
            throw new Error("Continue with Google before submitting this form.");
        }
        const firebase = await getFirebase();
        const currentUser = firebase.auth.currentUser;
        if (!currentUser || String(currentUser.email || "").toLowerCase()
                !== String(identity.email || "").toLowerCase()) {
            throw new Error("Your Google session changed. Continue with Google again.");
        }
        const response = await request(endpoint, "POST", Object.assign({}, profile, {
            email: currentUser.email,
            firebaseIdToken: await currentUser.getIdToken(true)
        }));
        if (response.ok) {
            await firebase.methods.signOut(firebase.auth);
        }
        return response;
    }

    async function logout() {
        const response = await request("/api/auth/logout", "POST");
        const config = await clientConfig().catch(function() { return null; });
        if (config && config.firebaseEnabled) {
            const firebase = await getFirebase();
            await firebase.methods.signOut(firebase.auth);
        }
        return response;
    }

    async function sendPasswordResetEmail(email) {
        const config = await clientConfig();
        if (!config.firebaseEnabled) {
            throw new Error("Firebase password reset is not enabled. Please contact support.");
        }
        const firebase = await getFirebase();
        return firebase.methods.sendPasswordResetEmail(
            firebase.auth,
            String(email || "").trim()
        );
    }

    window.RamjicartAuth = Object.freeze({
        currentUser: function() {
            return request("/api/auth/me", "GET");
        },
        login: login,
        startGoogleSignIn: startGoogleSignIn,
        loginWithGoogle: loginWithGoogle,
        logout: logout,
        sendPasswordResetEmail: sendPasswordResetEmail,
        registerCustomer: async function(profile, googleIdentity) {
            if (googleIdentity) return registerWithGoogle("/api/auth/register", profile, googleIdentity);
            const config = await clientConfig();
            if (!config.firebaseEnabled) return request("/api/auth/register", "POST", profile);
            return firebaseRegistration(
                profile, "/api/auth/register", profile.email, profile.password, profile.fullname
            );
        },
        registerRestaurant: async function(profile, googleIdentity) {
            if (googleIdentity) return registerWithGoogle("/api/restaurant/register", profile, googleIdentity);
            const config = await clientConfig();
            if (!config.firebaseEnabled) return request("/api/restaurant/register", "POST", profile);
            return firebaseRegistration(
                profile, "/api/restaurant/register", profile.email,
                profile.password, profile.ownerName
            );
        },
        registerDeliveryPartner: async function(profile, googleIdentity) {
            if (googleIdentity) return registerWithGoogle("/api/delivery/register", profile, googleIdentity);
            const config = await clientConfig();
            if (!config.firebaseEnabled) return request("/api/delivery/register", "POST", profile);
            return firebaseRegistration(
                profile, "/api/delivery/register", profile.email,
                profile.password, profile.name
            );
        }
    });

    if (typeof document !== "undefined" && !document.getElementById("globalGalaxyScript") && !document.getElementById("globalGalaxyCanvas")) {
        const s = document.createElement("script");
        s.id = "globalGalaxyScript";
        s.src = "/static/js/galaxy-bg.js";
        s.defer = true;
        document.head.appendChild(s);
    }
})();
