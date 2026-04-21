_logi() {
    local cur prev commands
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    commands="status watch info set button buttons gesture switch flow permissions profiles init apply daemon export import reset raw"

    case "${COMP_CWORD}" in
        1)
            COMPREPLY=($(compgen -W "$commands" -- "$cur"))
            ;;
        2)
            case "$prev" in
                set)
                    COMPREPLY=($(compgen -W "dpi speed smartshift smartshift-sensitivity scroll-speed scroll-direction thumb-speed thumb-direction thumb-smooth" -- "$cur"))
                    ;;
                button)
                    COMPREPLY=($(compgen -W "middle back forward gesture" -- "$cur"))
                    ;;
                gesture)
                    COMPREPLY=($(compgen -W "window media pan zoom app custom" -- "$cur"))
                    ;;
                export|import|apply|daemon|init)
                    COMPREPLY=($(compgen -f -- "$cur"))
                    ;;
                raw)
                    COMPREPLY=($(compgen -W "GET SET SUBSCRIBE" -- "$cur"))
                    ;;
            esac
            ;;
        3)
            case "${COMP_WORDS[1]}" in
                button)
                    COMPREPLY=($(compgen -W "back forward middle mission-control launchpad smart-zoom undo redo copy paste cut screenshot emoji search desktop close-tab do-not-disturb lookup switch-apps dictation gesture mode-shift" -- "$cur"))
                    ;;
            esac
            ;;
    esac
}

complete -F _logi logi
