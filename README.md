# Reading Guides

Interactive, beautifully designed study guides for remarkable books.

## 📚 Available Guides

| Book | Author | Language | Chapters |
|------|--------|----------|----------|
| [反脆弱 (Antifragile)](books/antifragile/index.html) | Nassim Nicholas Taleb | 中文 | 25 |

## 🗂 Structure

```
reading-guides/
├── index.html              # Book catalog landing page
├── css/
│   └── shared.css          # Shared design system
└── books/
    └── antifragile/        # Antifragile study guide
        ├── index.html      # Book landing page
        ├── css/
        │   └── chapter.css # Chapter page styles
        └── chapters/
            ├── ch01.html … ch25.html
```

## 🚀 View Online

**[https://emecii.github.io/reading-guides/](https://emecii.github.io/reading-guides/)**

## ➕ Adding a New Book

1. Create `books/<slug>/` with `index.html`, `css/chapter.css`, and `chapters/`
2. Link shared CSS with `../../css/shared.css`
3. Add an entry card in the root `index.html`

## 📄 License

Educational study guides. Original book content belongs to respective authors.
