// Top-level build file where you can add configuration options common to all sub-projects/modules.
plugins {
    alias(libs.plugins.android.application) apply false
    alias(libs.plugins.kotlin.android) apply false
    id("com.google.protobuf") version "0.9.4" apply false
    alias(libs.plugins.android.library) apply false // protobuf 플러그인 추가
}
