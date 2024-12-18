# Zola to Astro conversion

Zola and astro both uses Markdown with headers to write the blog.

```
+++
title = "Re:invent 2023 News"
template = "post.html"
in_search_index = true

[taxonomies]
tags = ["aws","dataengineering","reinvent"]
categories = ["aws","reinvent"]

[extra]
lead = "reinvent 23 news"
+++
```

While astro default uses the following schema

```
const blog = defineCollection({
	// Load Markdown and MDX files in the `src/content/blog/` directory.
	loader: glob({ base: './src/content/blog', pattern: '**/*.{md,mdx}' }),
	// Type-check frontmatter using a schema
	schema: z.object({
		title: z.string(),
		description: z.string(),
		// Transform string to Date object
		pubDate: z.coerce.date(),
		updatedDate: z.coerce.date().optional(),
		heroImage: z.string().optional(),
	}),
});
```

Reading from the following headers:
```
---
title: "Zola, Github Pages and CloudFlare"
description: "A comprehensive guide on setting up a personal blog using Zola static site generator, hosting it with GitHub Pages, and configuring CloudFlare for DNS and caching"
pubDate: 2022-01-26
author: Jacob
---
```

This needs some small changes and add a description.
Asked Claude to write this convertor and add the description if needed.

Note: This is pretty basic, you still need to change the image paths etc.
But it helped me doing the major part of the changes



## Basic conversion without AI generation

`uv run main.py input_directory output_directory --author "Your Name"`

## With AI generation for missing descriptions and tags

`yv run main.py input_directory output_directory --author "Your Name" --anthropic-key "your-api-key" --generate-missing`


```
uv run main.py \
  ./content/blog \
  ./src/content/blog \
  --author "Jacob" \
  --anthropic-key "your-api-key" \
  --generate-missing
```