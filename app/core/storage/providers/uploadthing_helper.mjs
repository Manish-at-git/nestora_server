import { UTApi } from "uploadthing/server";
import fs from "node:fs";

const token = (process.env.UPLOADTHING_TOKEN || "").trim().replace(/^['"]|['"]$/g, "");
const [filePath, fileName, fileType] = process.argv.slice(2);
if (!token || !filePath || !fs.existsSync(filePath)) {
  process.stdout.write(JSON.stringify({ ok: false, error: "UploadThing configuration or file is missing" }));
  process.exit(1);
}

try {
  const buffer = fs.readFileSync(filePath);
  const result = await new UTApi({ token }).uploadFiles(
    new File([buffer], fileName || "file.bin", { type: fileType || "application/octet-stream" })
  );
  if (result.error || !result.data) {
    throw new Error(result.error?.message || "UploadThing returned no data");
  }
  process.stdout.write(JSON.stringify({ ok: true, url: result.data.ufsUrl || result.data.url }));
} catch (error) {
  process.stdout.write(JSON.stringify({ ok: false, error: error.message || String(error) }));
  process.exit(1);
}
