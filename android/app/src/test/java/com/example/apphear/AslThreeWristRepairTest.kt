package com.example.apphear

import com.example.apphear.domain.texttoasl.AslFingerspellingBundle
import com.google.gson.JsonParser
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.file.Files
import java.nio.file.Path
import java.security.MessageDigest
import kotlin.math.*
import org.junit.Assert.*
import org.junit.Test

/** Full-path winding and byte preservation, not ASL validation. */
class AslThreeWristRepairTest {
 private val bytes=Files.readAllBytes(Path.of("src/aslOriginalWords/assets").resolve(AslFingerspellingBundle.PATH))
 private val buf=ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN)
 private val g=JsonParser.parseString(String(bytes,20,buf.getInt(12))).asJsonObject
 private val evidence=JsonParser.parseString(javaClass.getResource("/texttoasl/three-wrist-gates.json")!!.readText()).asJsonObject
 private fun raw(index:Int):ByteArray {
  val a=g.getAsJsonArray("accessors")[index].asJsonObject
  val v=g.getAsJsonArray("bufferViews")[a.get("bufferView").asInt].asJsonObject
  val width=when(a.get("type").asString){"SCALAR"->1;"VEC3"->3;"VEC4"->4;else->error("Accessor")}
  val offset=28+buf.getInt(12)+(v.get("byteOffset")?.asInt?:0)+(a.get("byteOffset")?.asInt?:0)
  return bytes.copyOfRange(offset,offset+a.get("count").asInt*width*4)
 }
 private fun floats(index:Int):List<Double> {
  val b=ByteBuffer.wrap(raw(index)).order(ByteOrder.LITTLE_ENDIAN)
  return (0 until b.capacity()/4).map{b.getFloat(it*4).toDouble()}
 }
 @Test fun allUnselectedAnimationsAndProtectedChannelsRemainExact() {
  assertEquals(AslFingerspellingBundle.BEFORE_INTEGRATION_SHA256,evidence.get("candidateSha256").asString)
  assertEquals(281,evidence.get("preservedActions").asInt)
  assertEquals(27,evidence.get("alphabetAndNeutralActionsUnchanged").asInt)
  val untouched=evidence.getAsJsonObject("unchangedActionSha256")
  val protected=evidence.getAsJsonObject("protectedNonArmChannelSha256")
  assertEquals(281,untouched.size());assertEquals(3,protected.size())
  val arms=listOf("Left","Right").flatMap{s->listOf("Arm","ForeArm","Hand").map{s+it}}.toSet()
  for(item in g.getAsJsonArray("animations").take(284)) {
   val a=item.asJsonObject;val name=a.get("name").asString;val d=MessageDigest.getInstance("SHA-256")
   if (WordHandRepairEvidence.accepts(name, g, bytes)) continue
   for(z in a.getAsJsonArray("channels")) {
    val ch=z.asJsonObject;val target=ch.getAsJsonObject("target");val node=target.get("node").asInt;val path=target.get("path").asString
    val nodeName=g.getAsJsonArray("nodes")[node].asJsonObject.get("name").asString
    val schoolFinger=name=="SIGN_SCHOOL" && listOf("Left","Right").any { side->listOf("Index","Middle","Ring","Pinky").any { finger->(1..3).any { nodeName==side+"Hand"+finger+it } } }
    if(protected.has(name)&&path=="rotation"&&(nodeName in arms || schoolFinger))continue
    d.update("$node:$path\u0000".toByteArray())
    val sampler=a.getAsJsonArray("samplers")[ch.get("sampler").asInt].asJsonObject
    d.update(raw(sampler.get("input").asInt));d.update(raw(sampler.get("output").asInt))
   }
   assertEquals(name,(if(untouched.has(name))untouched else protected).get(name).asString,d.digest().joinToString(""){"%02x".format(it)})
  }
  assertTrue(evidence.getAsJsonArray("surfaceChecks").single { it.asJsonObject.get("word").asString=="school" }.asJsonObject.get("wristBendDegrees").asDouble<60)
  assertTrue(evidence.get("schoolFingerCorrection").asBoolean)
  assertTrue(evidence.get("schoolFingerJointMaxBendDegrees").asDouble<5)
  assertTrue(evidence.getAsJsonArray("schoolContactVertexDistancesMeters").all { it.asDouble<.008 })
  assertFalse(evidence.get("qualifiedAslValidation").asBoolean)
 }
 @Test fun entireWristAndForearmTracksStayBelowHalfTurnExcursion() {
  val selected=setOf("SIGN_SCHOOL","SIGN_LIBRARY_HUMAN_AUTHORED_PREVIEW","SIGN_FINISH_HUMAN_AUTHORED_PREVIEW")
  for(item in g.getAsJsonArray("animations")) {
   val a=item.asJsonObject;val name=a.get("name").asString;if(name !in selected)continue
   for(z in a.getAsJsonArray("channels")) {
    val ch=z.asJsonObject;val t=ch.getAsJsonObject("target");val node=g.getAsJsonArray("nodes")[t.get("node").asInt].asJsonObject;val n=node.get("name").asString
    if(t.get("path").asString!="rotation" || n !in setOf("LeftHand","RightHand","LeftForeArm","RightForeArm"))continue
    val sampler=a.getAsJsonArray("samplers")[ch.get("sampler").asInt].asJsonObject
    val qs=floats(sampler.get("output").asInt).chunked(4)
    // Delta from bind rotation; unwrap swing/twist over the full track,
    // including release. Net endpoint equality alone missed the regression.
    val bind=node.getAsJsonArray("rotation")?.map{it.asDouble}?:listOf(0.0,0.0,0.0,1.0)
    val child=if(n.endsWith("Hand"))node else g.getAsJsonArray("nodes")[node.getAsJsonArray("children")[0].asInt].asJsonObject
    val axis=child.getAsJsonArray("translation").map{it.asDouble}.toDoubleArray()
    if(!n.endsWith("Hand")) {
     val q=bind;val cross=doubleArrayOf(q[1]*axis[2]-q[2]*axis[1],q[2]*axis[0]-q[0]*axis[2],q[0]*axis[1]-q[1]*axis[0])
     val twice=doubleArrayOf(q[1]*cross[2]-q[2]*cross[1],q[2]*cross[0]-q[0]*cross[2],q[0]*cross[1]-q[1]*cross[0])
     for(k in 0..2)axis[k]+=2*(q[3]*cross[k]+twice[k])
    }
    val length=sqrt(axis.sumOf{it*it});for(k in 0..2)axis[k]/=length
    var previous:Double?=null;val angles=mutableListOf<Double>()
    for(q in qs) {
     val inv=listOf(-bind[0],-bind[1],-bind[2],bind[3]);val delta=doubleArrayOf(q[3]*inv[0]+inv[3]*q[0]+q[1]*inv[2]-q[2]*inv[1],q[3]*inv[1]+inv[3]*q[1]+q[2]*inv[0]-q[0]*inv[2],q[3]*inv[2]+inv[3]*q[2]+q[0]*inv[1]-q[1]*inv[0],q[3]*inv[3]-q.take(3).zip(inv.take(3)).sumOf{it.first*it.second})
     var angle=2*atan2((0..2).sumOf{delta[it]*axis[it]},delta[3])
     previous?.let { p->while(angle-p>PI)angle-=2*PI;while(angle-p< -PI)angle+=2*PI }
     angles.add(angle);previous=angle
    }
    assertTrue("$name $n full excursion",Math.toDegrees(angles.max()-angles.min())<180)
   }
  }
 }
}
