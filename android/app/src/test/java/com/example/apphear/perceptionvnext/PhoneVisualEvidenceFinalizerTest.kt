package com.example.apphear.perceptionvnext

import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Test
import java.nio.file.Files
import java.util.concurrent.Executors

class PhoneVisualEvidenceFinalizerTest {
    @Test fun waitsForQueuedWritesBeforeCertifyingCount() {
        val directory = Files.createTempDirectory("phone-visual-drain").toFile()
        val writer = Executors.newSingleThreadExecutor()
        try {
            val futures = (1..3).map { ordinal ->
                writer.submit {
                    Thread.sleep(10)
                    directory.resolve("frame_${ordinal.toString().padStart(6, '0')}_original.jpg")
                        .writeBytes(byteArrayOf(1))
                }
            }
            assertEquals(3, PhoneVisualEvidenceFinalizer.awaitVerifiedOriginals(futures, directory, 3))
            assertThrows(IllegalArgumentException::class.java) {
                PhoneVisualEvidenceFinalizer.awaitVerifiedOriginals(futures, directory, 4)
            }
        } finally {
            writer.shutdownNow()
            directory.listFiles()?.forEach { it.delete() }
            directory.delete()
        }
    }
}
