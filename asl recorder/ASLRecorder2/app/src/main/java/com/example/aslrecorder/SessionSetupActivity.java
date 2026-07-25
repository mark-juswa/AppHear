package com.example.aslrecorder;

import android.content.Intent;
import android.os.Bundle;
import android.view.View;
import android.widget.ArrayAdapter;
import android.widget.Toast;
import android.widget.LinearLayout;
import android.widget.EditText;
import android.widget.CheckBox;
import android.text.InputType;
import androidx.appcompat.app.AlertDialog;

import androidx.appcompat.app.AppCompatActivity;

import com.example.aslrecorder.data.LabelsRepository;
import com.example.aslrecorder.data.MetadataManager;
import com.example.aslrecorder.databinding.ActivitySessionSetupBinding;
import com.example.aslrecorder.model.SessionConfig;
import com.example.aslrecorder.model.SignerProfile;

import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.List;
import java.util.Locale;

public class SessionSetupActivity extends AppCompatActivity {

    public static final String EXTRA_SIGNER = "extra_signer";
    public static final String EXTRA_CONFIG = "extra_config";

    private ActivitySessionSetupBinding binding;
    private MetadataManager metadataManager;
    private LabelsRepository labelsRepo;
    private SignerProfile signerProfile;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        binding = ActivitySessionSetupBinding.inflate(getLayoutInflater());
        setContentView(binding.getRoot());

        metadataManager = new MetadataManager(this);
        labelsRepo      = new LabelsRepository(this);

        signerProfile = (SignerProfile) getIntent().getSerializableExtra(EXTRA_SIGNER);
        if (signerProfile == null) { finish(); return; }

        binding.btnBack.setOnClickListener(v -> finish());

        binding.tvSignerInfo.setText(signerProfile.signerId
                + " · " + signerProfile.dominantHand + " hand");

        binding.btnChangeSigner.setOnClickListener(v -> {
            startActivity(new Intent(this, SignerProfileActivity.class));
            finish();
        });

        setupSpinners();
        updateSessionInfo();

        binding.spinnerSignLabel.setOnItemSelectedListener(
                new android.widget.AdapterView.OnItemSelectedListener() {
                    @Override
                    public void onItemSelected(android.widget.AdapterView<?> p,
                                               View v, int pos, long id) {
                        String label = (String) p.getItemAtPosition(pos);
                        boolean isBg = "Background".equalsIgnoreCase(label);
                        binding.layoutBgScenario.setVisibility(isBg ? View.VISIBLE : View.GONE);
                        // Background/rest needs a larger, varied set — default the target to 100.
                        if (isBg) binding.etTargetReps.setText("100");
                        updateSessionInfo();
                    }
                    @Override public void onNothingSelected(android.widget.AdapterView<?> p) {}
                });

        binding.btnStartRecording.setOnClickListener(v -> startRecording());
        binding.btnAddCustomSign.setOnClickListener(v -> showAddCustomSignDialog());
    }

    private void setupSpinners() {
        setSpinner(binding.spinnerSignLanguage,
                new String[]{"ASL", "FSL", "BSL", "ISL", "JSL", "CSL"});

        List<String> labels = labelsRepo.getAllLabels();
        ArrayAdapter<String> labelAdapter = new ArrayAdapter<>(
                this, android.R.layout.simple_spinner_item, labels.toArray(new String[0]));
        labelAdapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        binding.spinnerSignLabel.setAdapter(labelAdapter);

        setSpinner(binding.spinnerBgScenario,
                new String[]{"indoor_plain", "indoor_clutter", "outdoor", "office", "home"});
        setSpinner(binding.spinnerSpeed,
                new String[]{"normal", "slow", "fast"});
        setSpinner(binding.spinnerPosture,
                new String[]{"standing", "sitting"});
        setSpinner(binding.spinnerLighting,
                new String[]{"indoor_good", "indoor_dim", "outdoor", "side_lighting"});
        setSpinner(binding.spinnerBgType,
                new String[]{"plain_white", "plain_dark", "natural_busy", "other"});
    }

    private void setSpinner(android.widget.Spinner spinner, String[] items) {
        ArrayAdapter<String> adapter = new ArrayAdapter<>(
                this, android.R.layout.simple_spinner_item, items);
        adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        spinner.setAdapter(adapter);
    }

    private void updateSessionInfo() {
        String label   = (String) binding.spinnerSignLabel.getSelectedItem();
        int    session = metadataManager.getNextSessionNumber(
                signerProfile.signerId, label != null ? label : "");
        String id = signerProfile.signerId
                + "_Session" + String.format(Locale.US, "%03d", session)
                + (label != null ? "_" + label : "");
        binding.tvSessionInfo.setText(
                "Session " + String.format(Locale.US, "%03d", session) + " · " + id);
    }

    private void startRecording() {
        String label = (String) binding.spinnerSignLabel.getSelectedItem();
        if (label == null) {
            Toast.makeText(this, getString(R.string.error_select_label),
                    Toast.LENGTH_SHORT).show();
            return;
        }

        String repsStr = binding.etTargetReps.getText() == null
                ? "60" : binding.etTargetReps.getText().toString().trim();
        int targetReps;
        try {
            targetReps = Integer.parseInt(repsStr);
            if (targetReps < 1 || targetReps > 500) throw new NumberFormatException();
        } catch (NumberFormatException e) {
            binding.etTargetReps.setError(getString(R.string.error_invalid_reps));
            return;
        }

        SessionConfig config    = new SessionConfig();
        config.signLanguage     = (String) binding.spinnerSignLanguage.getSelectedItem();
        config.signLabel        = label;
        config.labelIndex       = labelsRepo.indexOf(label);
        config.targetReps       = targetReps;
        config.speed            = (String) binding.spinnerSpeed.getSelectedItem();
        config.posture          = (String) binding.spinnerPosture.getSelectedItem();
        config.distanceCm       = 70;  // fixed default — not collected from user
        config.lighting         = (String) binding.spinnerLighting.getSelectedItem();
        config.backgroundType   = (String) binding.spinnerBgType.getSelectedItem();
        config.shirtColor       = binding.etShirtColor.getText() == null
                ? "" : binding.etShirtColor.getText().toString().trim();
        config.signerId         = signerProfile.signerId;
        config.sessionNumber    = metadataManager.getNextSessionNumber(signerProfile.signerId, label);
        config.isBackground     = "Background".equalsIgnoreCase(label);
        if (config.isBackground) {
            config.bgScenario   = (String) binding.spinnerBgScenario.getSelectedItem();
        }
        config.recordingDate    = new SimpleDateFormat("yyyy-MM-dd", Locale.US)
                .format(new Date());

        Intent intent = new Intent(this, RecordingActivity.class);
        intent.putExtra(RecordingActivity.EXTRA_SIGNER, signerProfile);
        intent.putExtra(RecordingActivity.EXTRA_CONFIG, config);
        startActivity(intent);
    }

    private void showAddCustomSignDialog() {
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        int padding = (int) (16 * getResources().getDisplayMetrics().density);
        layout.setPadding(padding, padding, padding, padding);

        final EditText etSignName = new EditText(this);
        etSignName.setHint("Sign name (e.g. Tree)");
        etSignName.setInputType(InputType.TYPE_CLASS_TEXT);
        layout.addView(etSignName);

        final CheckBox cbTwoHanded = new CheckBox(this);
        cbTwoHanded.setText("Two-handed sign");
        cbTwoHanded.setPadding(0, 24, 0, 0);
        layout.addView(cbTwoHanded);

        new AlertDialog.Builder(this)
                .setTitle("Add Custom Sign")
                .setMessage("Enter the label name for the new sign. This will be saved to external storage config.")
                .setView(layout)
                .setPositiveButton("Add", (dialog, which) -> {
                    String name = etSignName.getText().toString().trim();
                    if (name.isEmpty()) {
                        Toast.makeText(this, "Name cannot be empty", Toast.LENGTH_SHORT).show();
                        return;
                    }
                    boolean isTwoHanded = cbTwoHanded.isChecked();

                    boolean success = labelsRepo.addCustomSign(this, name, isTwoHanded);
                    if (success) {
                        Toast.makeText(this, "Sign added successfully: " + name, Toast.LENGTH_SHORT).show();
                        // Reload spinner labels
                        List<String> labels = labelsRepo.getAllLabels();
                        ArrayAdapter<String> labelAdapter = new ArrayAdapter<>(
                                this, android.R.layout.simple_spinner_item, labels.toArray(new String[0]));
                        labelAdapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
                        binding.spinnerSignLabel.setAdapter(labelAdapter);

                        // Select the newly added label
                        int index = labels.indexOf(name);
                        if (index >= 0) {
                            binding.spinnerSignLabel.setSelection(index);
                        }
                    } else {
                        Toast.makeText(this, "Failed to add sign. Make sure it contains only letters/numbers/spaces/underscores and does not exist already.", Toast.LENGTH_LONG).show();
                    }
                })
                .setNegativeButton(android.R.string.cancel, null)
                .show();
    }
}
