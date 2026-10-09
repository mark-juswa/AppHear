package com.example.apphear.ui.profile

import android.content.Intent
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import android.os.Bundle
import android.view.View
import androidx.activity.OnBackPressedCallback
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import androidx.core.view.isVisible
import androidx.fragment.app.Fragment
import androidx.lifecycle.lifecycleScope
import com.example.apphear.R
import com.example.apphear.data.profile.AccountAvatarImages
import com.example.apphear.data.profile.AccountServices
import com.example.apphear.databinding.FragmentProfileBinding
import com.example.apphear.domain.profile.*
import com.example.apphear.ui.settings.AppConfiguration
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/** Restores the reference account panel and edits in the existing profile card. */
class ProfileAccountContent(private val fragment: Fragment) {
    private var binding: FragmentProfileBinding? = null
    private val repository get() = AccountServices.repository(fragment.requireContext())
    private var editing = false
    private var signup = false
    private var busy = false
    private var selectedAvatar: Uri? = null
    private var avatarJob: Job? = null
    private var loadedAvatar = ""
    private var refreshSettings: (() -> Unit)? = null
    private var restoredDraft: Bundle? = null
    private var back: OnBackPressedCallback? = null
    private val picker = fragment.registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null && binding != null && repository.profile.value != null) {
            try { fragment.requireContext().contentResolver.takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION) }
            catch (_: SecurityException) { /* Temporary grants remain usable for the current edit. */ }
            selectedAvatar = uri
            editing = true
            renderProfile(repository.profile.value, false)
            previewAvatar(uri)
        }
    }

    fun attach(value: FragmentProfileBinding, saved: Bundle?, settings: () -> Unit) {
        binding = value
        restoredDraft = saved
        signup = saved?.getBoolean("account_signup") ?: false
        refreshSettings = settings
        value.profileAuth.root.isVisible = saved?.getBoolean("account_auth_open") ?: false
        value.profileScroll.isVisible = !value.profileAuth.root.isVisible
        value.profileEditButton.setOnClickListener {
            if (busy) return@setOnClickListener
            if (repository.profile.value == null) showAuth(true)
            else if (editing) saveProfile()
            else { editing = true; renderProfile(repository.profile.value, false) }
        }
        value.profileCancelEdit.setOnClickListener {
            editing = false; selectedAvatar = null; loadedAvatar = ""
            renderProfile(repository.profile.value, true)
        }
        value.avatarPicker.setOnClickListener {
            if (!busy && repository.profile.value != null) picker.launch(arrayOf("image/*"))
        }
        value.profileLogoutButton.setOnClickListener {
            execute(false) {
                val revoked = repository.logout()
                editing = false; selectedAvatar = null
                renderProfile(null, true)
                value.tvProfileStatus.setText(if (revoked) R.string.profile_account_logout else R.string.profile_account_logout_offline)
            }
        }
        val auth = value.profileAuth
        auth.tabLogin.setOnClickListener { setSignup(false) }
        auth.tabRegister.setOnClickListener { setSignup(true) }
        auth.tvToggleAuth.setOnClickListener { setSignup(!signup) }
        auth.profileAuthGuest.setOnClickListener { if (!busy) showAuth(false) }
        auth.btnAuthPrimary.setOnClickListener { submitAuth() }
        back = object : OnBackPressedCallback(false) {
            override fun handleOnBackPressed() {
                if (busy) return
                if (binding?.profileAuth?.root?.isVisible == true) showAuth(false)
                else { editing = false; selectedAvatar = null; loadedAvatar = ""; renderProfile(repository.profile.value, true) }
            }
        }.also { fragment.requireActivity().onBackPressedDispatcher.addCallback(fragment.viewLifecycleOwner, it) }
        renderAuth()
        fragment.viewLifecycleOwner.lifecycleScope.launch {
            repository.profile.collect { profile ->
                val draft = restoredDraft
                if (draft != null && profile != null && draft.getString("account_draft_id") == profile.id) {
                    editing = draft.getBoolean("account_editing")
                    renderProfile(profile, true)
                    value.inputFullName.setText(draft.getString("account_draft_name", profile.fullName))
                    value.inputProfileUsername.setText(draft.getString("account_draft_username", profile.username))
                    selectedAvatar = draft.getString("account_draft_avatar")?.let(Uri::parse)
                    selectedAvatar?.let(::previewAvatar)
                    restoredDraft = null
                } else renderProfile(profile, !editing)
                refreshSettings?.invoke()
            }
        }
        execute(false) {
            value.tvProfileStatus.setText(R.string.profile_account_restoring)
            repository.restore()
            if (repository.profile.value != null) value.tvProfileStatus.text = ""
            else value.tvProfileStatus.setText(R.string.profile_account_guest_body)
        }
    }

    private fun submitAuth() {
        val b = binding ?: return
        val a = b.profileAuth
        val email = a.inputEmail.text.toString().trim()
        val password = a.inputPassword.text.toString()
        val confirmation = a.inputConfirmPassword.text.toString()
        val username = a.inputUsername.text.toString()
        val registering = signup
        val remember = a.cbRemember.isChecked
        execute(true) {
            val signedIn = if (registering) repository.signup(username, email, password, confirmation)
                else { repository.login(email, password, remember); true }
            a.inputPassword.text.clear()
            a.inputConfirmPassword.text.clear()
            if (signedIn) { showAuth(false); renderProfile(repository.profile.value, true) }
            else { setSignup(false); a.tvAuthStatus.setText(R.string.profile_account_confirmation) }
        }
    }

    private fun saveProfile() {
        val b = binding ?: return
        val username = b.inputProfileUsername.text.toString()
        val name = b.inputFullName.text.toString()
        val uri = selectedAvatar
        execute(false) {
            AccountValidation.profile(username, name)
            val jpeg = uri?.let { withContext(Dispatchers.IO) { AccountAvatarImages.prepare(fragment.requireContext(), it) } }
            repository.saveProfile(username, name, jpeg)
            selectedAvatar = null; editing = false; loadedAvatar = ""
            renderProfile(repository.profile.value, true)
            b.tvProfileStatus.setText(R.string.profile_account_saved)
        }
    }

    private fun execute(auth: Boolean, operation: suspend () -> Unit) {
        if (busy) return
        busy = true
        updateControls()
        fragment.viewLifecycleOwner.lifecycleScope.launch {
            try { operation() }
            catch (error: CancellationException) { throw error }
            catch (error: Exception) {
                val issue = (error as? AccountException)?.issue ?: AccountIssue.SERVER
                val b = binding
                if (b != null) {
                    val message = fragment.getString(issueString(issue))
                    if (auth) b.profileAuth.tvAuthStatus.text = message else b.tvProfileStatus.text = message
                    if (repository.profile.value == null) { editing = false; selectedAvatar = null; renderProfile(null, true) }
                }
            } finally { busy = false; if (binding != null) updateControls() }
        }
    }

    private fun renderProfile(profile: AccountProfile?, replaceFields: Boolean) {
        val b = binding ?: return
        val signedIn = profile != null
        b.tvUsername.text = profile?.displayName ?: fragment.getString(R.string.profile_guest_display_name)
        b.tvUserMeta.text = profile?.email ?: fragment.getString(R.string.profile_guest_meta)
        if (replaceFields) {
            b.inputFullName.setText(profile?.fullName.orEmpty())
            b.inputProfileUsername.setText(profile?.username.orEmpty())
            b.inputProfileEmail.setText(profile?.email.orEmpty())
        }
        if (editing && signedIn) b.tvProfileStatus.setText(R.string.profile_account_edit_hint)
        b.profileLogoutButton.isVisible = signedIn
        if (profile == null || (selectedAvatar == null && profile.avatarUrl.isEmpty())) {
            b.imgProfileAvatar.setImageResource(R.drawable.account)
            b.imgProfileAvatar.setColorFilter(ContextCompat.getColor(fragment.requireContext(), R.color.white))
            val padding = (22 * fragment.resources.displayMetrics.density).toInt()
            b.imgProfileAvatar.setPadding(padding, padding, padding, padding)
            loadedAvatar = ""
        } else if (selectedAvatar == null && profile.avatarUrl != loadedAvatar) {
            b.imgProfileAvatar.setImageResource(R.drawable.account)
            loadedAvatar = profile.avatarUrl
            loadAvatar(profile.avatarUrl)
        }
        updateControls()
    }

    private fun updateControls() {
        val b = binding ?: return
        val signedIn = repository.profile.value != null
        b.inputFullName.isEnabled = editing && signedIn && !busy
        b.inputProfileUsername.isEnabled = editing && signedIn && !busy
        b.inputProfileEmail.isEnabled = false
        b.profileEditButton.isEnabled = !busy
        b.profileCancelEdit.isVisible = editing && signedIn
        b.profileCancelEdit.isEnabled = !busy
        b.avatarPicker.isEnabled = signedIn && !busy
        b.profileLogoutButton.isEnabled = !busy
        b.profileEditLabel.setText(when {
            busy && editing -> R.string.profile_account_saving
            busy -> R.string.profile_account_loading
            !signedIn -> R.string.profile_account_sign_in
            editing -> R.string.profile_account_save
            else -> R.string.profile_edit_profile
        })
        val a = b.profileAuth
        listOf(a.btnAuthPrimary, a.tabLogin, a.tabRegister, a.tvToggleAuth, a.profileAuthGuest,
            a.inputUsername, a.inputEmail, a.inputPassword, a.inputConfirmPassword, a.cbRemember).forEach { it.isEnabled = !busy }
        a.tvAuthPrimary.setText(if (busy) R.string.profile_account_loading else if (signup) R.string.profile_auth_signup else R.string.profile_auth_login)
        back?.isEnabled = editing || a.root.isVisible
    }

    private fun setSignup(value: Boolean) {
        signup = value
        binding?.profileAuth?.tvAuthStatus?.text = ""
        renderAuth()
    }

    private fun renderAuth() {
        val a = binding?.profileAuth ?: return
        a.inputUsername.isVisible = signup
        a.inputConfirmPassword.isVisible = signup
        a.cbRemember.isVisible = !signup
        a.tvAuthTitle.setText(if (signup) R.string.profile_auth_register_heading else R.string.profile_auth_login_heading)
        a.tvAuthSubtitle.setText(if (signup) R.string.profile_auth_register_body else R.string.profile_auth_login_body)
        a.tvToggleAuth.setText(if (signup) R.string.profile_auth_existing else R.string.profile_auth_create)
        a.tabLogin.setBackgroundResource(if (signup) android.R.color.transparent else R.drawable.profile_auth_segment_active)
        a.tabRegister.setBackgroundResource(if (signup) R.drawable.profile_auth_segment_active else android.R.color.transparent)
        val active = ContextCompat.getColor(fragment.requireContext(), R.color.color_text_primary)
        val inactive = ContextCompat.getColor(fragment.requireContext(), R.color.color_text_secondary)
        a.tvTabLogin.setTextColor(if (signup) inactive else active)
        a.tvTabRegister.setTextColor(if (signup) active else inactive)
        updateControls()
    }

    private fun showAuth(show: Boolean) {
        val a = binding?.profileAuth ?: return
        a.root.isVisible = show
        binding?.profileScroll?.isVisible = !show
        if (!show) {
            a.inputPassword.text.clear(); a.inputConfirmPassword.text.clear()
            val input = fragment.requireContext().getSystemService(android.content.Context.INPUT_METHOD_SERVICE) as android.view.inputmethod.InputMethodManager
            input.hideSoftInputFromWindow(a.root.windowToken, 0)
        }
        updateControls()
    }

    private fun previewAvatar(uri: Uri) {
        avatarJob?.cancel()
        avatarJob = fragment.viewLifecycleOwner.lifecycleScope.launch {
            try {
                val bitmap = withContext(Dispatchers.IO) {
                    val jpeg = AccountAvatarImages.prepare(fragment.requireContext(), uri)
                    BitmapFactory.decodeByteArray(jpeg, 0, jpeg.size)
                }
                if (selectedAvatar == uri) displayAvatar(bitmap)
            } catch (error: CancellationException) { throw error }
            catch (_: Exception) { binding?.tvProfileStatus?.setText(R.string.profile_account_error_avatar) }
        }
    }

    private fun loadAvatar(url: String) {
        avatarJob?.cancel()
        avatarJob = fragment.viewLifecycleOwner.lifecycleScope.launch {
            try {
                val bitmap = withContext(Dispatchers.IO) { AccountAvatarImages.fetch(url, AppConfiguration.supabaseUrl) }
                if (url == repository.profile.value?.avatarUrl && selectedAvatar == null) displayAvatar(bitmap)
            } catch (error: CancellationException) { throw error }
            catch (_: Exception) { if (!editing) binding?.tvProfileStatus?.setText(R.string.profile_account_avatar_unavailable) }
        }
    }

    private fun displayAvatar(bitmap: Bitmap?) {
        val image = binding?.imgProfileAvatar ?: return
        if (bitmap == null) return
        image.setPadding(0, 0, 0, 0)
        image.clearColorFilter()
        image.setImageBitmap(bitmap)
    }

    fun saveState(out: Bundle) {
        val b = binding ?: return
        out.putBoolean("account_auth_open", b.profileAuth.root.isVisible)
        out.putBoolean("account_signup", signup)
        out.putBoolean("account_editing", editing)
        if (editing) {
            out.putString("account_draft_id", repository.profile.value?.id)
            out.putString("account_draft_name", b.inputFullName.text.toString())
            out.putString("account_draft_username", b.inputProfileUsername.text.toString())
            out.putString("account_draft_avatar", selectedAvatar?.toString())
        }
    }

    fun close() {
        avatarJob?.cancel()
        binding?.profileAuth?.inputPassword?.text?.clear()
        binding?.profileAuth?.inputConfirmPassword?.text?.clear()
        binding = null
        back = null
        refreshSettings = null
        editing = false
        selectedAvatar = null
        loadedAvatar = ""
    }

    private fun issueString(issue: AccountIssue) = when (issue) {
        AccountIssue.CONFIGURATION -> R.string.profile_account_error_config
        AccountIssue.NETWORK -> R.string.profile_account_error_network
        AccountIssue.CREDENTIALS -> R.string.profile_account_error_credentials
        AccountIssue.EMAIL_UNCONFIRMED -> R.string.profile_account_error_unconfirmed
        AccountIssue.RATE_LIMIT -> R.string.profile_account_error_rate
        AccountIssue.SIGNUP_DISABLED -> R.string.profile_account_error_signup
        AccountIssue.PASSWORD_POLICY -> R.string.profile_account_error_password
        AccountIssue.CAPTCHA -> R.string.profile_account_error_captcha
        AccountIssue.SESSION_EXPIRED -> R.string.profile_account_error_session
        AccountIssue.STORAGE -> R.string.profile_account_error_storage
        AccountIssue.AVATAR -> R.string.profile_account_error_avatar
        AccountIssue.SERVER -> R.string.profile_account_error_server
        AccountIssue.INVALID_INPUT -> R.string.profile_account_error_input
    }
}
