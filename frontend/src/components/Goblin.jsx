import { useEffect, useState } from "react";

/**
 * Goblin sprite — sits next to the greeting on Home.
 * Ambient life: 10% movement, 90% stillness.
 *  - Slow breathing (scale 1 ↔ 1.018, ~4s loop)
 *  - Subtle sway (rotate ±0.4deg, ~9s loop, offset)
 *  - Mood = time-of-day → CSS filter (warm/neutral/amber/cool)
 *  - Rare blink (every 5–12s, brief vertical squash on the upper half)
 */

function timeOfDay() {
  const h = new Date().getHours();
  if (h >= 5 && h < 11) return "morning";
  if (h >= 11 && h < 17) return "midday";
  if (h >= 17 && h < 23) return "evening";
  return "late_night";
}

const MOOD = {
  morning:    { filter: "brightness(1.02) saturate(1.05) sepia(0.06)",                       caption: "slow start", sprite: "/goblin-morning.png" },
  midday:     { filter: "brightness(1.0) saturate(1.0)",                                      caption: "",            sprite: "/goblin.png" },
  evening:    { filter: "brightness(0.96) saturate(1.08) sepia(0.14) hue-rotate(-6deg)",      caption: "settling",    sprite: "/goblin-evening.png" },
  late_night: { filter: "brightness(0.85) saturate(0.85) hue-rotate(8deg) contrast(1.05)",    caption: "still up",    sprite: "/goblin-late_night.png" },
};

export default function Goblin({ size = 200, className = "" }) {
  const [mood, setMood] = useState(timeOfDay());
  const [blinking, setBlinking] = useState(false);

  // Re-check mood every 10 minutes (in case the user leaves the tab open)
  useEffect(() => {
    const id = setInterval(() => setMood(timeOfDay()), 10 * 60 * 1000);
    return () => clearInterval(id);
  }, []);

  // Random blink loop
  useEffect(() => {
    let cancelled = false;
    const scheduleBlink = () => {
      const delay = 4500 + Math.random() * 7500; // 4.5–12s
      setTimeout(() => {
        if (cancelled) return;
        setBlinking(true);
        setTimeout(() => {
          if (cancelled) return;
          setBlinking(false);
          scheduleBlink();
        }, 140);
      }, delay);
    };
    scheduleBlink();
    return () => { cancelled = true; };
  }, []);

  const m = MOOD[mood];

  return (
    <div
      className={`goblin-wrap ${className}`}
      data-testid="goblin"
      data-mood={mood}
      style={{
        width: size,
        height: size,
        position: "relative",
        filter: m.filter,
      }}
    >
      <div className="goblin-breathe">
        <div className="goblin-sway">
          <img
            src={m.sprite}
            alt="emotional support goblin"
            draggable={false}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "contain",
              userSelect: "none",
              transformOrigin: "50% 100%",
              transform: blinking ? "scaleY(0.985)" : "scaleY(1)",
              transition: "transform 90ms ease-in-out, opacity 1.2s ease",
            }}
          />
        </div>
      </div>
      {/* Blink overlay: a thin amber-warm bar across the eyes for 140ms */}
      {blinking && (
        <div
          aria-hidden="true"
          style={{
            position: "absolute",
            left: "30%",
            right: "30%",
            top: "30%",
            height: "5%",
            background: "rgba(22, 24, 22, 0.9)",
            borderRadius: "999px",
            pointerEvents: "none",
            filter: "blur(2px)",
          }}
        />
      )}
    </div>
  );
}
