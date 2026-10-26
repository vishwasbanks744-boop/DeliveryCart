/**
 * Ramjicart - Global Galaxy / Space Background
 * Runs seamlessly on all pages behind the site content.
 * Position: fixed, inset: 0, z-index: -1, pointer-events: none.
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
                background-color: #05010f !important;
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
                background: radial-gradient(ellipse at 50% 25%, #1a0b3b 0%, #0d0422 55%, #05010f 100%);
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
        let nextShootingStarTime = performance.now() + 2500 + Math.random() * 2000;

        // Palette: mostly white (65%), soft orange #ff8a5c (18%), soft purple #b79cff (17%)
        const STAR_COLORS = [
            { r: 255, g: 255, b: 255, weight: 0.65 },
            { r: 255, g: 138, b: 92,  weight: 0.18 },
            { r: 183, g: 156, b: 255, weight: 0.17 }
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
            // 3 large blurry nebula clouds (purple, pink/orange, deep indigo)
            nebulae = [
                {
                    baseXRatio: 0.20,
                    baseYRatio: 0.35,
                    radiusRatio: 0.45,
                    colorInner: "rgba(147, 51, 234, 0.13)",   // cosmic purple
                    colorMid: "rgba(88, 28, 135, 0.04)",
                    driftSpeedX: 0.00035,
                    driftSpeedY: 0.0005,
                    driftAmpX: 50,
                    driftAmpY: 30,
                    phaseX: 0,
                    phaseY: 1.1
                },
                {
                    baseXRatio: 0.82,
                    baseYRatio: 0.45,
                    radiusRatio: 0.40,
                    colorInner: "rgba(255, 110, 60, 0.10)",   // pink / warm orange
                    colorMid: "rgba(220, 65, 30, 0.03)",
                    driftSpeedX: 0.00045,
                    driftSpeedY: 0.00035,
                    driftAmpX: 40,
                    driftAmpY: 35,
                    phaseX: 2.3,
                    phaseY: 0.4
                },
                {
                    baseXRatio: 0.50,
                    baseYRatio: 0.75,
                    radiusRatio: 0.50,
                    colorInner: "rgba(99, 102, 241, 0.11)",   // deep mystic indigo
                    colorMid: "rgba(59, 130, 246, 0.03)",
                    driftSpeedX: 0.0003,
                    driftSpeedY: 0.00045,
                    driftAmpX: 55,
                    driftAmpY: 25,
                    phaseX: 1.6,
                    phaseY: 2.8
                }
            ];
        }

        function createStars() {
            stars = [];
            const isMobile = width < 768;
            // Mobile: ~80-100 stars; Desktop: ~200-300 stars
            const starCount = isMobile
                ? Math.floor(Math.min(100, Math.max(80, (width * height) / 8000)))
                : Math.floor(Math.min(300, Math.max(200, (width * height) / 4500)));

            for (let i = 0; i < starCount; i++) {
                const color = pickColor();
                const layerRoll = Math.random();
                let layer, radius, baseAlpha, twinkleSpeed, twinkleAmp;

                if (layerRoll < 0.60) {
                    // Layer 1: tiny background stars (subtle drift, high density)
                    layer = 1;
                    radius = 0.5 + Math.random() * 0.7; // 0.5 - 1.2px
                    baseAlpha = 0.3 + Math.random() * 0.4;
                    twinkleSpeed = 0.006 + Math.random() * 0.015;
                    twinkleAmp = 0.12 + Math.random() * 0.18;
                } else if (layerRoll < 0.85) {
                    // Layer 2: medium twinkling stars (distinct shimmer)
                    layer = 2;
                    radius = 1.2 + Math.random() * 0.7; // 1.2 - 1.9px
                    baseAlpha = 0.45 + Math.random() * 0.4;
                    twinkleSpeed = 0.02 + Math.random() * 0.04;
                    twinkleAmp = 0.28 + Math.random() * 0.32;
                } else {
                    // Layer 3: large glowing stars (soft radial glow halo)
                    layer = 3;
                    radius = 2.0 + Math.random() * 1.0; // 2.0 - 3.0px
                    baseAlpha = 0.65 + Math.random() * 0.35;
                    twinkleSpeed = 0.012 + Math.random() * 0.028;
                    twinkleAmp = 0.18 + Math.random() * 0.22;
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
                    vx: (Math.random() - 0.5) * 0.04,
                    vy: (Math.random() - 0.5) * 0.03
                });
            }
        }

        function spawnShootingStar(now) {
            const angle = (Math.PI / 180) * (26 + Math.random() * 18); // 26° to 44° downward
            const speed = 9 + Math.random() * 6;
            const startX = Math.random() * (width * 0.8);
            const startY = Math.random() * (height * 0.4);
            const length = 90 + Math.random() * 80;
            const duration = 850 + Math.random() * 500; // ms

            const tintRoll = Math.random();
            let tint = { r: 255, g: 255, b: 255 };
            if (tintRoll < 0.35) tint = { r: 255, g: 155, b: 105 }; // soft orange
            else if (tintRoll < 0.65) tint = { r: 195, g: 170, b: 255 }; // soft purple

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
                    const glowRadius = s.radius * 3.6;
                    const glow = ctx.createRadialGradient(s.x, s.y, 0, s.x, s.y, glowRadius);
                    glow.addColorStop(0, `rgba(${s.color.r}, ${s.color.g}, ${s.color.b}, ${s.baseAlpha * 0.45})`);
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
                const cx = width * n.baseXRatio + driftX + currentPX * 8;
                const cy = height * n.baseYRatio + driftY + currentPY * 6;
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
                const currentAlpha = Math.max(0.1, Math.min(1, s.baseAlpha + Math.sin(s.twinklePhase) * s.twinkleAmp));

                let pOffsetX = 0;
                let pOffsetY = 0;
                if (s.layer === 1) {
                    pOffsetX = currentPX * 5;
                    pOffsetY = currentPY * 3;
                } else if (s.layer === 2) {
                    pOffsetX = currentPX * 11;
                    pOffsetY = currentPY * 7;
                } else {
                    pOffsetX = currentPX * 22;
                    pOffsetY = currentPY * 14;
                }

                const drawX = s.x + pOffsetX;
                const drawY = s.y + pOffsetY;

                if (s.layer === 3) {
                    const glowRadius = s.radius * 3.6;
                    const glow = ctx.createRadialGradient(drawX, drawY, 0, drawX, drawY, glowRadius);
                    glow.addColorStop(0, `rgba(${s.color.r}, ${s.color.g}, ${s.color.b}, ${currentAlpha * 0.45})`);
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

            // 3. Shooting stars (meteors every 3-5 seconds)
            if (now >= nextShootingStarTime) {
                spawnShootingStar(now);
                nextShootingStarTime = now + 3000 + Math.random() * 2000;
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
                streakGrad.addColorStop(0.7, `rgba(${ss.tint.r}, ${ss.tint.g}, ${ss.tint.b}, ${alpha * 0.6})`);
                streakGrad.addColorStop(1, `rgba(255, 255, 255, ${alpha * 0.95})`);

                ctx.lineWidth = 1.8;
                ctx.strokeStyle = streakGrad;
                ctx.lineCap = "round";
                ctx.beginPath();
                ctx.moveTo(tailX, tailY);
                ctx.lineTo(ss.x, ss.y);
                ctx.stroke();

                const headGlow = ctx.createRadialGradient(ss.x, ss.y, 0, ss.x, ss.y, 6);
                headGlow.addColorStop(0, `rgba(255, 255, 255, ${alpha})`);
                headGlow.addColorStop(0.4, `rgba(${ss.tint.r}, ${ss.tint.g}, ${ss.tint.b}, ${alpha * 0.5})`);
                headGlow.addColorStop(1, "rgba(0, 0, 0, 0)");
                ctx.fillStyle = headGlow;
                ctx.beginPath();
                ctx.arc(ss.x, ss.y, 6, 0, Math.PI * 2);
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

        function pauseAnimation() {
            isRunning = false;
            if (animId) {
                cancelAnimationFrame(animId);
                animId = null;
            }
        }

        function resumeAnimation() {
            if (!isRunning && !document.hidden && !prefersReducedMotion) {
                startAnimation();
            }
        }

        // Resize with debounce
        let resizeTimer = null;
        window.addEventListener("resize", () => {
            clearTimeout(resizeTimer);
            resizeTimer = setTimeout(() => {
                resize();
                if (prefersReducedMotion) renderStatic();
            }, 120);
        }, { passive: true });

        // Tab hidden / visibility handling
        document.addEventListener("visibilitychange", () => {
            if (document.hidden) {
                pauseAnimation();
            } else {
                resumeAnimation();
            }
        });

        // Reduced motion preference
        motionQuery.addEventListener("change", (e) => {
            prefersReducedMotion = e.matches;
            if (prefersReducedMotion) {
                pauseAnimation();
                renderStatic();
            } else {
                resumeAnimation();
            }
        });

        // Initialize and start
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
