package com.example.apphear.fingerspelling

import org.junit.Assert.*
import org.junit.Test
import java.nio.ByteBuffer

class UprightRgbaSourceTest {
    @Test fun allRotationsPreservePixelChiralityStridesAndBufferPosition() {
        val buffer=ByteBuffer.allocate(50)
        val base=3; val row=20; val pixel=6
        for(y in 0..1) for(x in 0..2) {
            buffer.put(base+y*row+x*pixel,(10*y+x).toByte())
            buffer.put(base+y*row+x*pixel+1,(40+y).toByte())
            buffer.put(base+y*row+x*pixel+2,(70+x).toByte())
        }
        buffer.position(base)
        val expected=mapOf(0 to arrayOf(intArrayOf(0,1,2),intArrayOf(10,11,12)),
            90 to arrayOf(intArrayOf(10,0),intArrayOf(11,1),intArrayOf(12,2)),
            180 to arrayOf(intArrayOf(12,11,10),intArrayOf(2,1,0)),
            270 to arrayOf(intArrayOf(2,12),intArrayOf(1,11),intArrayOf(0,10)))
        for((rotation,grid) in expected) {
            val source=UprightRgbaSource(3,2,row,pixel,rotation,buffer)
            for(y in grid.indices) for(x in grid[0].indices) assertEquals(grid[y][x].toFloat(),source.channel(x,y,0),0f)
            assertEquals(base,buffer.position())
        }
    }
}
