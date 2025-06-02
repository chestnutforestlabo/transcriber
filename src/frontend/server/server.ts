import express, { type Request, type Response } from "express"
import fs from "fs"
import path from "path"
import { fileURLToPath } from "url"

const app = express()
const PORT = process.env.PORT || 3001

// Get the directory name properly in ES modules
const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

interface SaveTranscriptRequest {
  filename: string
  data: Array<{
    start: number
    end: number
    speaker: string | null
    text: string
  }>
}

app.use(express.json({ limit: "10mb" }))

// Add CORS headers for local development
app.use((req, res, next) => {
  res.header("Access-Control-Allow-Origin", "*")
  res.header("Access-Control-Allow-Headers", "Origin, X-Requested-With, Content-Type, Accept")
  res.header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")

  // Handle preflight requests
  if (req.method === "OPTIONS") {
    return res.status(200).end()
  }

  next()
})

// Debug endpoint to check directory structure and permissions
app.get("/api/debug", async (_req: Request, res: Response) => {
  try {
    const transcriptsDir = path.join(__dirname, "..", "public", "transcripts")
    const files = await fs.promises.readdir(transcriptsDir)

    // Check if directory exists and is writable
    const dirStats = await fs.promises.stat(transcriptsDir)
    const isDir = dirStats.isDirectory()
    const isWritable = await fs.promises
      .access(transcriptsDir, fs.constants.W_OK)
      .then(() => true)
      .catch(() => false)

    // Get current working directory
    const cwd = process.cwd()

    return res.json({
      success: true,
      cwd,
      transcriptsDir,
      isDir,
      isWritable,
      files,
    })
  } catch (error) {
    console.error("Debug error:", error)
    return res.status(500).json({ error: "Debug failed", details: (error as Error).message })
  }
})

app.post("/api/save-transcript", async (req: Request, res: Response) => {
  try {
    // 受信したリクエストボディをすべて出力
    console.log("=== /api/save-transcript 受信データ ===")
    console.log(JSON.stringify(req.body, null, 2))

    const { filename, data, speakerMapping } = req.body as SaveTranscriptRequest & { speakerMapping?: any }
    console.log("Received request to save transcript:", filename)

    // Validate input
    if (!filename || !data || !Array.isArray(data)) {
      console.error("Invalid input:", { filename, dataType: typeof data, isArray: Array.isArray(data) })
      return res.status(400).json({ error: "Invalid input. Filename and data array are required." })
    }

    // Security check: ensure filename only contains allowed characters and is in the transcripts directory
    const sanitizedFilename = path.basename(filename)
    if (sanitizedFilename !== filename) {
      console.error("Invalid filename:", filename)
      return res.status(400).json({ error: "Invalid filename." })
    }

    // ファイルパス構築
    const projectRoot = process.cwd()
    const filePath = path.join(projectRoot, "public", "transcripts", sanitizedFilename)
    console.log("Writing to file path:", filePath)

    // バックアップファイルを作成（既存ファイルがある場合）
    try {
      await fs.promises.access(filePath, fs.constants.F_OK)
      const backupPath = `${filePath}.backup`
      await fs.promises.copyFile(filePath, backupPath)
      console.log("Created backup at:", backupPath)
    } catch (error) {
      console.log("No existing file to backup or error creating backup:", error)
    }

    // ファイル書き込み - 同期的に書き込みを行い、確実に完了させる
    try {
      fs.writeFileSync(filePath, JSON.stringify(data, null, 2), "utf8")
      console.log("Successfully saved transcript to:", filePath)
    } catch (writeError) {
      console.error("Error writing file:", writeError)
      return res.status(500).json({ error: "Failed to write file", details: (writeError as Error).message })
    }

    // 書き込み確認
    try {
      await fs.promises.access(filePath, fs.constants.F_OK)
      console.log("File exists after writing")
    } catch (error) {
      console.error("File does not exist after writing attempt:", error)
      return res.status(500).json({ error: "File write verification failed", details: (error as Error).message })
    }

    return res.json({ success: true, path: filePath })
  } catch (error) {
    console.error("Error saving transcript:", error)
    return res.status(500).json({ error: "Failed to save transcript.", details: (error as Error).message })
  }
})

// Add a simple test endpoint
app.get("/api/test", (_req: Request, res: Response) => {
  res.json({ message: "API server is running" })
})

app.listen(PORT, () => {
  console.log(`Server listening on port ${PORT}`)
  console.log(`Current working directory: ${process.cwd()}`)

  // Log the transcripts directory path
  const transcriptsDir = path.join(process.cwd(), "public", "transcripts")
  console.log(`Transcripts directory: ${transcriptsDir}`)

  // Check if the directory exists
  fs.access(transcriptsDir, fs.constants.F_OK, (err) => {
    if (err) {
      console.error(`Transcripts directory does not exist: ${transcriptsDir}`)

      // Try to create the directory
      fs.mkdir(transcriptsDir, { recursive: true }, (mkdirErr) => {
        if (mkdirErr) {
          console.error(`Failed to create transcripts directory: ${mkdirErr.message}`)
        } else {
          console.log(`Created transcripts directory: ${transcriptsDir}`)
        }
      })
    } else {
      console.log(`Transcripts directory exists: ${transcriptsDir}`)

      // Check if the directory is writable
      fs.access(transcriptsDir, fs.constants.W_OK, (writeErr) => {
        if (writeErr) {
          console.error(`Transcripts directory is not writable: ${writeErr.message}`)
        } else {
          console.log(`Transcripts directory is writable`)
        }
      })
    }
  })
})
