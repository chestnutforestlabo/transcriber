// 画像モーダルコンポーネント
"use client"

import { useState, useEffect } from "react"
import type React from "react"

interface ImageModalProps {
  src: string
  alt: string
  isOpen: boolean
  onClose: () => void
}

const ImageModal: React.FC<ImageModalProps> = ({ src, alt, isOpen, onClose }) => {
  const [isVisible, setIsVisible] = useState(false)

  useEffect(() => {
    if (isOpen) {
      setIsVisible(true)
      document.body.style.overflow = "hidden"
    } else {
      const timer = setTimeout(() => {
        setIsVisible(false)
      }, 300)
      document.body.style.overflow = ""
      return () => clearTimeout(timer)
    }
  }, [isOpen])

  if (!isVisible) return null

  return (
    <div className={`image-modal-overlay ${isOpen ? "open" : "closing"}`} onClick={onClose}>
      <div className="image-modal-content" onClick={(e) => e.stopPropagation()}>
        <button className="image-modal-close" onClick={onClose}>
          &times;
        </button>
        <img src={src || "/placeholder.svg"} alt={alt} className="image-modal-img" />
      </div>
    </div>
  )
}

export default ImageModal