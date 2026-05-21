// Lightweight markdown rendering — just bold (**x**), italic (*x*), and inline code (`x`)
// Used by chat messages and letter rendering. Keeps things on-tone (no full markdown lib).
import React from "react";

export function renderInline(text) {
  if (text == null) return null;
  // Pattern matches **bold**, *italic*, or `code` (non-greedy)
  const re = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g;
  const parts = text.split(re);
  return parts.map((part, i) => {
    if (!part) return null;
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={i} className="text-moss-50 font-semibold">{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith("*") && part.endsWith("*") && part.length > 2) {
      return <em key={i}>{part.slice(1, -1)}</em>;
    }
    if (part.startsWith("`") && part.endsWith("`")) {
      return <code key={i} className="text-amber/90 bg-moss-800/60 px-1 rounded">{part.slice(1, -1)}</code>;
    }
    return <React.Fragment key={i}>{part}</React.Fragment>;
  });
}

export function renderBody(text) {
  if (!text) return null;
  const lines = text.split("\n");
  return lines.map((line, i) => {
    const trim = line.trim();
    if (!trim) return <div key={i} className="h-2" />;
    const numMatch = trim.match(/^(\d+)[.)]\s+(.+)$/);
    if (numMatch) {
      return (
        <div key={i} className="flex gap-3 text-moss-100">
          <span className="text-amber font-heading shrink-0">{numMatch[1]}.</span>
          <span>{renderInline(numMatch[2])}</span>
        </div>
      );
    }
    if (/^[-*]\s+/.test(trim)) {
      return (
        <div key={i} className="text-moss-100 pl-4 relative before:absolute before:left-0 before:top-2 before:w-1.5 before:h-1.5 before:rounded-full before:bg-amber/70">
          {renderInline(trim.replace(/^[-*]\s+/, ""))}
        </div>
      );
    }
    return <p key={i} className="text-moss-100 leading-relaxed">{renderInline(trim)}</p>;
  });
}

// strip markdown for short previews
export function stripMd(text) {
  if (!text) return "";
  return text
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/\*([^*]+)\*/g, "$1")
    .replace(/`([^`]+)`/g, "$1");
}
