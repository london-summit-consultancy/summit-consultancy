// Chapter copy choreography. Continuous visibility is scrubbed (reversible)
// from scroll; discrete entrance accents are authored anime.js timelines fired
// once per chapter entry. The copy itself is server-rendered HTML — this file
// only moves it.
import { animate, stagger } from "animejs";

import { smoothstep } from "../utils/maths.js";

export class Overlay {
  constructor(root) {
    this.sections = Array.from(root.querySelectorAll("[data-chapter]")).sort(
      (a, b) => Number(a.dataset.chapter) - Number(b.dataset.chapter)
    );
    this.inners = this.sections.map(
      (section) => section.querySelector(".exp-copy") || section.firstElementChild
    );
    this.cue = root.querySelector(".experience-cue");
    this.lastChapter = -1;
  }

  update(chapter, local, p) {
    const count = this.sections.length;
    for (let i = 0; i < count; i++) {
      const inner = this.inners[i];
      if (!inner) continue;
      let opacity = 0;
      let rise = 0;
      if (i === chapter) {
        const fadeIn = i === 0 ? 1 : smoothstep(0.03, 0.16, local);
        const fadeOut = i === count - 1 ? 1 : 1 - smoothstep(0.78, 0.93, local);
        opacity = fadeIn * fadeOut;
        rise = (1 - fadeIn) * 18 - (1 - fadeOut) * 12;
      }
      inner.style.opacity = String(opacity);
      inner.style.transform = `translateY(${rise.toFixed(2)}px)`;
      // Chapters stack absolutely — an invisible one must never intercept
      // clicks meant for the active chapter's links/CTAs.
      inner.style.visibility = opacity > 0.02 ? "visible" : "hidden";
    }

    if (chapter !== this.lastChapter) {
      const wasBackward = chapter < this.lastChapter;
      this.lastChapter = chapter;
      if (!wasBackward) this._accent(chapter);
    }

    if (this.cue) this.cue.style.opacity = String(1 - smoothstep(0.004, 0.03, p));
  }

  _accent(chapter) {
    const inner = this.inners[chapter];
    if (!inner) return;
    const targets = inner.querySelectorAll(".exp-reveal");
    if (!targets.length) return;
    animate(targets, {
      y: [24, 0],
      opacity: [0, 1],
      delay: stagger(200),
      duration: 1200,
      ease: "outExpo",
    });
  }
}
