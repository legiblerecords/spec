// Each spec page takes its title and summary from the spec file, and its
// Markdown copy and llms-full.txt use the spec's text, not this template.
export default {
  eleventyComputed: {
    permalink: (data) => data.specDoc.url,
    title: (data) => data.specDoc.title,
    lede: (data) => data.specDoc.lede,
    generatedMarkdown: (data) => data.specDoc.markdown,
  },
};
