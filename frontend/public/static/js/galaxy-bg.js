/**
 * Ramjicart - Global Galaxy / Space Background
 * Runs seamlessly on all pages behind the site content.
 * Position: fixed, inset: 0, z-index: -1, pointer-events: none.
 * Designed to be subtle, soft, and dim ("halka halka") so it feels like
 * an authentic celestial galaxy floating in the background without being harsh or heavy ("gaadha").
 */
(function() {
    if (typeof window === "undefined" || typeof document === "undefined") return;

    function setupCanvas() {
        if (document.getElementById("globalGalaxyCanvas")) return;

        // Ensure html and body let the fixed canvas shine through
        const style = document.createElement("style");
        style.id = "globalGalaxyStyle";
        style.textContent = `
            html {
                background-color: #070412 !important;
            }
            body {
                background-color: transparent !important;
            }
            #globalGalaxyCanvas {
                position: fixed;
                top: 0;
                left: 0;
                width: 100vw;
                height: 100vh;
                z-index: -1;
                pointer-events: none;
                display: block;
                background: radial-gradient(ellipse at 50% 20%, #160e33 0%, #0d0822 50%, #070412 100%);
            }
        `;
        document.head.appendChild(style);

        const canvas = document.createElement("canvas");
        canvas.id = "globalGalaxyCanvas";
        canvas.setAttribute("aria-hidden", "true");
        if (document.body) {
            document.body.prepend(canvas);
        } else {
            document.addEventListener("DOMContentLoaded", () => document.body.prepend(canvas));
        }

        initEngine(canvas);
    }

    function initEngine(canvas) {
        const ctx = canvas.getContext("2d");
        if (!ctx) return;

        let width = 0;
        let height = 0;
        let dpr = 1;
        let animId = null;
        let isRunning = false;

        // Accessibility: prefers-reduced-motion
        const motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
        let prefersReducedMotion = motionQuery.matches;

        // Parallax state
        let targetPX = 0;
        let targetPY = 0;
        let currentPX = 0;
        let currentPY = 0;

        // Star layers & entities
        let stars = [];
        let nebulae = [];
        let shootingStars = [];
        let nextShootingStarTime = performance.now() + 3000 + Math.random() * 2500;

        // Soft celestial palette: delicate white (70%), soft starlight warm peach (15%), soft lavender (15%)
        const STAR_COLORS = [
            { r: 255, g: 255, b: 255, weight: 0.70 },
            { r: 255, g: 205, b: 165, weight: 0.15 },
            { r: 215, g: 200, b: 255, weight: 0.15 }
        ];

        function pickColor() {
            const rand = Math.random();
            let acc = 0;
            for (let i = 0; i < STAR_COLORS.length; i++) {
                acc += STAR_COLORS[i].weight;
                if (rand <= acc) return STAR_COLORS[i];
            }
            return STAR_COLORS[0];
        }

        function initNebulae() {
            // 3 wide, ultra-soft, ethereal cosmic clouds (faint dust, not heavy blobs)
            nebulae = [
                {
                    baseXRatio: 0.20,
                    baseYRatio: 0.35,
                    radiusRatio: 0.55,
                    colorInner: "rgba(130, 60, 215, 0.048)",   // ethereal purple dust
                    colorMid: "rgba(75, 25, 125, 0.015)",
                    driftSpeedX: 0.00025,
                    driftSpeedY: 0.00035,
                    driftAmpX: 40,
                    driftAmpY: 25,
                    phaseX: 0,
                    phaseY: 1.1
                },
                {
                    baseXRatio: 0.82,
                    baseYRatio: 0.45,
                    radiusRatio: 0.50,
                    colorInner: "rgba(255, 130, 80, 0.035)",   // warm subtle stardust
                    colorMid: "rgba(200, 70, 35, 0.010)",
                    driftSpeedX: 0.00030,
                    driftSpeedY: 0.00025,
                    driftAmpX: 35,
                    driftAmpY: 30,
                    phaseX: 2.3,
                    phaseY: 0.4
                },
                {
                    baseXRatio: 0.50,
                    baseYRatio: 0.75,
                    radiusRatio: 0.60,
                    colorInner: "rgba(90, 110, 240, 0.040)",   // deep mystic indigo dust
                    colorMid: "rgba(50, 75, 180, 0.012)",
                    driftSpeedX: 0.00020,
                    driftSpeedY: 0.00030,
                    driftAmpX: 45,
                    driftAmpY: 20,
                    phaseX: 1.6,
                    phaseY: 2.8
                }
            ];
        }

        function createStars() {
            stars = [];
            const isMobile = width < 768;
            // Mobile: ~55-75 stars; Desktop: ~130-180 stars
            const starCount = isMobile
                ? Math.floor(Math.min(75, Math.max(55, (width * height) / 10000)))
                : Math.floor(Math.min(180, Math.max(130, (width * height) / 6000)));

            for (let i = 0; i < starCount; i++) {
                const color = pickColor();
                const layerRoll = Math.random();
                let layer, radius, baseAlpha, twinkleSpeed, twinkleAmp;

                if (layerRoll < 0.65) {
                    // Layer 1: tiny background cosmic dust (faint, gentle shimmer)
                    layer = 1;
                    radius = 0.35 + Math.random() * 0.45; // 0.35 - 0.8px
                    baseAlpha = 0.12 + Math.random() * 0.20; // 0.12 - 0.32
                    twinkleSpeed = 0.008 + Math.random() * 0.016;
                    twinkleAmp = 0.06 + Math.random() * 0.09;
                } else if (layerRoll < 0.88) {
                    // Layer 2: delicate twinkling stars (soft diamond shimmer)
                    layer = 2;
                    radius = 0.75 + Math.random() * 0.45; // 0.75 - 1.2px
                    baseAlpha = 0.22 + Math.random() * 0.26; // 0.22 - 0.48
                    twinkleSpeed = 0.016 + Math.random() * 0.030;
                    twinkleAmp = 0.10 + Math.random() * 0.15;
                } else {
                    // Layer 3: gentle glowing stars (subtle, soft halo - NOT giant gaadha blobs!)
                    layer = 3;
                    radius = 1.15 + Math.random() * 0.40; // 1.15 - 1.55px
                    baseAlpha = 0.35 + Math.random() * 0.22; // 0.35 - 0.57
                    twinkleSpeed = 0.010 + Math.random() * 0.020;
                    twinkleAmp = 0.09 + Math.random() * 0.12;
                }

                stars.push({
                    x: Math.random() * width,
                    y: Math.random() * height,
                    radius: radius,
                    layer: layer,
                    color: color,
                    baseAlpha: baseAlpha,
                    alpha: baseAlpha,
                    twinkleSpeed: twinkleSpeed,
                    twinkleAmp: twinkleAmp,
                    twinklePhase: Math.random() * Math.PI * 2,
                    vx: (Math.random() - 0.5) * 0.025,
                    vy: (Math.random() - 0.5) * 0.020
                });
            }
        }

        function spawnShootingStar(now) {
            const angle = (Math.PI / 180) * (26 + Math.random() * 18); // 26° to 44° downward
            const speed = 7.5 + Math.random() * 4.5;
            const startX = Math.random() * (width * 0.85);
            const startY = Math.random() * (height * 0.35);
            const length = 65 + Math.random() * 55;
            const duration = 900 + Math.random() * 400; // ms

            const tintRoll = Math.random();
            let tint = { r: 255, g: 255, b: 255 };
            if (tintRoll < 0.35) tint = { r: 255, g: 205, b: 175 }; // soft peach
            else if (tintRoll < 0.70) tint = { r: 220, g: 205, b: 255 }; // soft lavender

            shootingStars.push({
                x: startX,
                y: startY,
                dx: Math.cos(angle) * speed,
                dy: Math.sin(angle) * speed,
                length: length,
                angle: angle,
                startTime: now,
                duration: duration,
                tint: tint
            });
        }

        function resize() {
            width = window.innerWidth || document.documentElement.clientWidth || 1200;
            height = window.innerHeight || document.documentElement.clientHeight || 800;
            dpr = Math.min(window.devicePixelRatio || 1, 2);

            canvas.width = Math.floor(width * dpr);
            canvas.height = Math.floor(height * dpr);
            canvas.style.width = width + "px";
            canvas.style.height = height + "px";
            ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

            initNebulae();
            createStars();
        }

        // Parallax on mouse move
        window.addEventListener("mousemove", (e) => {
            targetPX = ((e.clientX / width) - 0.5) * 2;
            targetPY = ((e.clientY / height) - 0.5) * 2;
        }, { passive: true });

        // Static frame for prefers-reduced-motion
        function renderStatic() {
            ctx.clearRect(0, 0, width, height);

            // Nebulae
            ctx.save();
            ctx.globalCompositeOperation = "screen";
            for (let i = 0; i < nebulae.length; i++) {
                const n = nebulae[i];
                const cx = width * n.baseXRatio;
                const cy = height * n.baseYRatio;
                const radius = Math.max(width, height) * n.radiusRatio;

                const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, radius);
                grad.addColorStop(0, n.colorInner);
                grad.addColorStop(0.55, n.colorMid);
                grad.addColorStop(1, "rgba(0, 0, 0, 0)");

                ctx.fillStyle = grad;
                ctx.beginPath();
                ctx.arc(cx, cy, radius, 0, Math.PI * 2);
                ctx.fill();
            }
            ctx.restore();

            // Stars
            for (let i = 0; i < stars.length; i++) {
                const s = stars[i];
                if (s.layer === 3) {
                    const glowRadius = s.radius * 2.0;
                    const glow = ctx.createRadialGradient(s.x, s.y, 0, s.x, s.y, glowRadius);
                    glow.addColorStop(0, `rgba(${s.color.r}, ${s.color.g}, ${s.color.b}, ${s.baseAlpha * 0.18})`);
                    glow.addColorStop(1, "rgba(0, 0, 0, 0)");
                    ctx.fillStyle = glow;
                    ctx.beginPath();
                    ctx.arc(s.x, s.y, glowRadius, 0, Math.PI * 2);
                    ctx.fill();
                }

                ctx.fillStyle = `rgba(${s.color.r}, ${s.color.g}, ${s.color.b}, ${s.baseAlpha})`;
                ctx.beginPath();
                ctx.arc(s.x, s.y, s.radius, 0, Math.PI * 2);
                ctx.fill();
            }
        }

        // Animation loop
        let lastTime = performance.now();

        function animate(now) {
            if (!isRunning) return;

            const delta = Math.min(now - lastTime, 64);
            lastTime = now;

            ctx.clearRect(0, 0, width, height);

            // Parallax lerp
            currentPX += (targetPX - currentPX) * 0.05;
            currentPY += (targetPY - currentPY) * 0.05;

            // 1. Nebula clouds
            ctx.save();
            ctx.globalCompositeOperation = "screen";
            for (let i = 0; i < nebulae.length; i++) {
                const n = nebulae[i];
                const driftX = Math.sin(now * n.driftSpeedX + n.phaseX) * n.driftAmpX;
                const driftY = Math.cos(now * n.driftSpeedY + n.phaseY) * n.driftAmpY;
                const cx = width * n.baseXRatio + driftX + currentPX * 6;
                const cy = height * n.baseYRatio + driftY + currentPY * 5;
                const radius = Math.max(width, height) * n.radiusRatio;

                const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, radius);
                grad.addColorStop(0, n.colorInner);
                grad.addColorStop(0.55, n.colorMid);
                grad.addColorStop(1, "rgba(0, 0, 0, 0)");

                ctx.fillStyle = grad;
                ctx.beginPath();
                ctx.arc(cx, cy, radius, 0, Math.PI * 2);
                ctx.fill();
            }
            ctx.restore();

            // 2. 3 Layers of Stars
            for (let i = 0; i < stars.length; i++) {
                const s = stars[i];

                s.x += s.vx * (delta / 16);
                s.y += s.vy * (delta / 16);
                if (s.x < -10) s.x = width + 10;
                if (s.x > width + 10) s.x = -10;
                if (s.y < -10) s.y = height + 10;
                if (s.y > height + 10) s.y = -10;

                s.twinklePhase += s.twinkleSpeed * (delta / 16);
                const currentAlpha = Math.max(0.08, Math.min(1, s.baseAlpha + Math.sin(s.twinklePhase) * s.twinkleAmp));

                let pOffsetX = 0;
                let pOffsetY = 0;
                if (s.layer === 1) {
                    pOffsetX = currentPX * 4;
                    pOffsetY = currentPY * 2.5;
                } else if (s.layer === 2) {
                    pOffsetX = currentPX * 8;
                    pOffsetY = currentPY * 5;
                } else {
                    pOffsetX = currentPX * 15;
                    pOffsetY = currentPY * 10;
                }

                const drawX = s.x + pOffsetX;
                const drawY = s.y + pOffsetY;

                if (s.layer === 3) {
                    const glowRadius = s.radius * 2.0;
                    const glow = ctx.createRadialGradient(drawX, drawY, 0, drawX, drawY, glowRadius);
                    glow.addColorStop(0, `rgba(${s.color.r}, ${s.color.g}, ${s.color.b}, ${currentAlpha * 0.18})`);
                    glow.addColorStop(1, "rgba(0, 0, 0, 0)");
                    ctx.fillStyle = glow;
                    ctx.beginPath();
                    ctx.arc(drawX, drawY, glowRadius, 0, Math.PI * 2);
                    ctx.fill();
                }

                ctx.fillStyle = `rgba(${s.color.r}, ${s.color.g}, ${s.color.b}, ${currentAlpha})`;
                ctx.beginPath();
                ctx.arc(drawX, drawY, s.radius, 0, Math.PI * 2);
                ctx.fill();
            }

            // 3. Shooting stars (meteors every 3.5 - 6 seconds)
            if (now >= nextShootingStarTime) {
                spawnShootingStar(now);
                nextShootingStarTime = now + 3500 + Math.random() * 2500;
            }

            for (let i = shootingStars.length - 1; i >= 0; i--) {
                const ss = shootingStars[i];
                const elapsed = now - ss.startTime;
                const progress = elapsed / ss.duration;

                if (progress >= 1 || ss.x > width + 100 || ss.y > height + 100) {
                    shootingStars.splice(i, 1);
                    continue;
                }

                ss.x += ss.dx * (delta / 16);
                ss.y += ss.dy * (delta / 16);

                let alpha = 1;
                if (progress < 0.2) {
                    alpha = progress / 0.2;
                } else if (progress > 0.6) {
                    alpha = 1 - (progress - 0.6) / 0.4;
                }
                alpha = Math.max(0, Math.min(1, alpha));

                const tailX = ss.x - Math.cos(ss.angle) * ss.length;
                const tailY = ss.y - Math.sin(ss.angle) * ss.length;

                ctx.save();
                ctx.globalCompositeOperation = "lighter";

                const streakGrad = ctx.createLinearGradient(tailX, tailY, ss.x, ss.y);
                streakGrad.addColorStop(0, "rgba(255, 255, 255, 0)");
                streakGrad.addColorStop(0.7, `rgba(${ss.tint.r}, ${ss.tint.g}, ${ss.tint.b}, ${alpha * 0.35})`);
                streakGrad.addColorStop(1, `rgba(255, 255, 255, ${alpha * 0.65})`);

                ctx.lineWidth = 1.1;
                ctx.strokeStyle = streakGrad;
                ctx.lineCap = "round";
                ctx.beginPath();
                ctx.moveTo(tailX, tailY);
                ctx.lineTo(ss.x, ss.y);
                ctx.stroke();

                const headGlow = ctx.createRadialGradient(ss.x, ss.y, 0, ss.x, ss.y, 3.5);
                headGlow.addColorStop(0, `rgba(255, 255, 255, ${alpha * 0.8})`);
                headGlow.addColorStop(0.4, `rgba(${ss.tint.r}, ${ss.tint.g}, ${ss.tint.b}, ${alpha * 0.3})`);
                headGlow.addColorStop(1, "rgba(0, 0, 0, 0)");
                ctx.fillStyle = headGlow;
                ctx.beginPath();
                ctx.arc(ss.x, ss.y, 3.5, 0, Math.PI * 2);
                ctx.fill();

                ctx.restore();
            }

            animId = requestAnimationFrame(animate);
        }

        function startAnimation() {
            if (isRunning || prefersReducedMotion) return;
            isRunning = true;
            lastTime = performance.now();
            animId = requestAnimationFrame(animate);
        }

        function stopAnimation() {
            if (!isRunning) return;
            isRunning = false;
            if (animId) {
                cancelAnimationFrame(animId);
                animId = null;
            }
        }

        // Reduced motion preference listener
        if (motionQuery.addEventListener) {
            motionQuery.addEventListener("change", (e) => {
                prefersReducedMotion = e.matches;
                if (prefersReducedMotion) {
                    stopAnimation();
                    renderStatic();
                } else {
                    startAnimation();
                }
            });
        }

        // Visibilitychange listener: pause animation when page is hidden
        document.addEventListener("visibilitychange", () => {
            if (document.hidden) {
                stopAnimation();
            } else if (!prefersReducedMotion) {
                startAnimation();
            }
        });

        // Resize debounced
        let resizeTimer = null;
        window.addEventListener("resize", () => {
            clearTimeout(resizeTimer);
            resizeTimer = setTimeout(() => {
                resize();
                if (prefersReducedMotion) {
                    renderStatic();
                }
            }, 100);
        }, { passive: true });

        // Initial setup
        resize();
        if (prefersReducedMotion) {
            renderStatic();
        } else {
            startAnimation();
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", setupCanvas);
    } else {
        setupCanvas();
    }
})();
