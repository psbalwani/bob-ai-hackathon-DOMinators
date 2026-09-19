/** Trigger a browser "Save file" for text fetched via an authenticated
 * axios call, since a plain `<a href>` to an auth-gated endpoint would
 * issue an unauthenticated request and get a 401. */
export function downloadTextFile(filename: string, text: string, mimeType = "text/plain") {
  const blob = new Blob([text], { type: mimeType })
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}
