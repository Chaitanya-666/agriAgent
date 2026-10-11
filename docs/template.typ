// Shared style for all AgriAgent documents. Import with:
//   #import "template.typ": *
//   #show: doc.with(title: "...", subtitle: "...")

#let accent = rgb("#2f6b3a")
#let muted = rgb("#5b6470")

#let doc(title: "", subtitle: "", date: "11 October 2026", body) = {
  set document(title: title, author: "AgriAgent Team")
  set page(
    paper: "a4",
    margin: (x: 2.2cm, y: 2.4cm),
    header: context {
      if counter(page).get().first() > 1 [
        #set text(8pt, fill: muted)
        AgriAgent #h(1fr) #title
      ]
    },
    footer: context [
      #set text(8pt, fill: muted)
      #h(1fr) #counter(page).display("1 / 1", both: true)
    ],
  )
  set text(font: "Libertinus Serif", size: 10.5pt, lang: "en")
  set par(justify: true, leading: 0.62em)
  set heading(numbering: "1.1")
  show heading.where(level: 1): it => {
    v(0.8em)
    set text(14pt, fill: accent)
    it
    v(0.2em)
  }
  show heading.where(level: 2): set text(11.5pt)
  show raw.where(block: false): box.with(fill: luma(240), inset: (x: 2pt), outset: (y: 2pt), radius: 2pt)
  show raw.where(block: true): block.with(fill: luma(245), inset: 8pt, radius: 3pt, width: 100%)
  show link: set text(fill: accent)
  set table(stroke: 0.5pt + luma(180), inset: 6pt)
  show table.cell.where(y: 0): set text(weight: "bold")

  // Title block
  block(width: 100%, inset: (bottom: 10pt), stroke: (bottom: 1.5pt + accent))[
    #text(20pt, weight: "bold", fill: accent)[#title] \
    #v(2pt)
    #text(11pt, fill: muted)[#subtitle] \
    #text(9pt, fill: muted)[AgriAgent Final Year Project · #date]
  ]
  v(6pt)
  body
}

// Status badges used in evidence tables.
#let badge(label, color) = box(
  fill: color.lighten(80%),
  stroke: 0.6pt + color,
  inset: (x: 4pt, y: 2pt),
  radius: 2pt,
  text(8pt, weight: "bold", fill: color.darken(20%))[#label],
)
#let real = badge("REAL", rgb("#2f8f46"))
#let mock = badge("MOCK", rgb("#c27c0e"))
#let planned = badge("PLANNED", rgb("#5b6470"))
#let blocked = badge("BLOCKED", rgb("#b3261e"))
#let partial = badge("PARTIAL", rgb("#1f6fb2"))

// Callout boxes.
#let note(title: "Note", body) = block(
  width: 100%,
  fill: rgb("#eef5ef"),
  stroke: (left: 3pt + accent),
  inset: 9pt,
  radius: (right: 3pt),
)[*#title.* #body]

#let warn(title: "Warning", body) = block(
  width: 100%,
  fill: rgb("#fdf1ef"),
  stroke: (left: 3pt + rgb("#b3261e")),
  inset: 9pt,
  radius: (right: 3pt),
)[*#title.* #body]

// A pipeline stage box for simple flow diagrams.
#let stage(name, detail, color: accent) = box(
  width: 100%,
  stroke: 0.8pt + color,
  fill: color.lighten(90%),
  inset: 7pt,
  radius: 3pt,
)[#text(weight: "bold")[#name] \ #text(8.5pt, fill: muted)[#detail]]

#let down = align(center, text(12pt, fill: muted)[↓])
