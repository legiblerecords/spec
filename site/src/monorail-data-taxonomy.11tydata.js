// The page's Markdown copy and llms-full.txt use the generated Markdown, not the template.
export default {
  eleventyComputed: {
    generatedMarkdown: (data) => data.monorailTaxonomy.markdown,
  },
};
