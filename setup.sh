#!/bin/bash

macos::check_or_install() {
    if ! command -v $1 >/dev/null; then
        if [[ $# == 2 ]]; then
            brew install $2
        else
            brew install $1
        fi
    fi
}

macos::setup() {
    HOMEBREW_NO_AUTO_UPDATE=1
    if ! command -v brew >/dev/null; then
        echo "Homebrew is need to setup: https://brew.sh/"
        exit 1
    fi
    macos::check_or_install adb android-platform-tools
    macos::check_or_install ffmpeg
    macos::check_or_install exiftool
}

linux::check_or_install() {
    local install
    if command -v apt >/dev/null; then
        install="apt install -y"
    elif command -v dnf >/dev/null; then
        install="dnf install -y"
    elif command -v yum >/dev/null; then
        install="yum install -y"
    else
        echo "Unknown Linux distribution"
        exit 1
    fi
    if ! command -v $1 >/dev/null; then
        if [[ $# == 2 ]]; then
            sudo $install $2
        else
            sudo $install $1
        fi
    fi
}

linux::setup() {
    linux::check_or_install adb android-platform-tools
    linux::check_or_install ffmpeg
    linux::check_or_install exiftool
}

main() {
    if [[ $(uname) == Darwin ]]; then
        macos::setup
    elif [[ $(uname) == Linux ]]; then
        linux::setup
    else
        echo "Unsupported system $(uname)."
        exit 1
    fi
}

main "$@"
