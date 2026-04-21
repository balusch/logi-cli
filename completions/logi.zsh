#compdef logi

_logi() {
    local -a commands
    commands=(
        'status:Show live device status'
        'watch:Watch real-time device events'
        'info:Show agent and system info'
        'set:Set a device parameter'
        'button:Set a button action'
        'buttons:Show button assignments'
        'profiles:List profiles'
        'export:Export device config to JSON'
        'import:Import device config from JSON'
        'raw:Send raw request to agent'
    )

    local -a set_params
    set_params=(dpi speed smartshift smartshift-sensitivity scroll-speed scroll-direction)

    local -a button_names
    button_names=(middle back forward gesture)

    local -a actions
    actions=(
        back forward middle mission-control launchpad smart-zoom
        undo redo copy paste cut screenshot emoji search
        desktop close-tab do-not-disturb lookup switch-apps
        dictation gesture mode-shift
    )

    _arguments -C \
        '1:command:->command' \
        '*::arg:->args'

    case $state in
        command)
            _describe 'command' commands
            ;;
        args)
            case $words[1] in
                set)
                    case $CURRENT in
                        2) _describe 'parameter' set_params ;;
                    esac
                    ;;
                button)
                    case $CURRENT in
                        2) _describe 'button' button_names ;;
                        3) _describe 'action' actions ;;
                    esac
                    ;;
                buttons|button)
                    _arguments '--profile[Profile name]:profile:(safari chrome excel powerpoint word zoom)'
                    ;;
                export)
                    _files -g '*.json'
                    ;;
                import)
                    _files -g '*.json'
                    ;;
                raw)
                    case $CURRENT in
                        2) _describe 'verb' '(GET SET SUBSCRIBE)' ;;
                    esac
                    ;;
            esac
            ;;
    esac
}

_logi
