package com.example.aslrecorder.model;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.Serializable;

public class SignerProfile implements Serializable {

    public String signerId;       // e.g. "S01"
    public String ageGroup;       // "18-25" | "25-35" | "35-50"
    public String gender;         // "Male" | "Female" | "Other" | "Prefer not to say"
    public String dominantHand;   // "Right" | "Left"
    public String signExperience; // "None" | "Some" | "Experienced"
    public String handSize;       // "Small" | "Medium" | "Large"
    public String splitAssignment;// "train" | "val" | "test"
    public String notes;

    public SignerProfile() {}

    public SignerProfile(String signerId) {
        this.signerId = signerId;
        this.ageGroup = "18-25";
        this.gender = "Prefer not to say";
        this.dominantHand = "Right";
        this.signExperience = "None";
        this.handSize = "Medium";
        this.splitAssignment = "train";
        this.notes = "";
    }

    public JSONObject toJson() throws JSONException {
        JSONObject obj = new JSONObject();
        obj.put("signer_id", signerId);
        obj.put("age_group", ageGroup);
        obj.put("gender", gender);
        obj.put("dominant_hand", dominantHand);
        obj.put("sign_experience", signExperience);
        obj.put("hand_size", handSize);
        obj.put("split_assignment", splitAssignment);
        obj.put("notes", notes != null ? notes : "");
        return obj;
    }

    public static SignerProfile fromJson(JSONObject obj) throws JSONException {
        SignerProfile p = new SignerProfile();
        p.signerId        = obj.optString("signer_id", "");
        p.ageGroup        = obj.optString("age_group", "18-25");
        p.gender          = obj.optString("gender", "Prefer not to say");
        p.dominantHand    = obj.optString("dominant_hand", "Right");
        p.signExperience  = obj.optString("sign_experience", "None");
        p.handSize        = obj.optString("hand_size", "Medium");
        p.splitAssignment = obj.optString("split_assignment", "train");
        p.notes           = obj.optString("notes", "");
        return p;
    }

    public boolean isValid() {
        return signerId != null && !signerId.trim().isEmpty()
                && splitAssignment != null && !splitAssignment.isEmpty();
    }

    @Override
    public String toString() {
        return signerId + " (" + dominantHand + " hand, " + splitAssignment + ")";
    }
}
