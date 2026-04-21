#compdef logi

_logi() {
    local -a commands
    commands=(
        'status:Show live device status'
        'watch:Watch real-time device events'
        'info:Show agent and system info'
        'set:Set a device parameter'
        'button:Remap a mouse button'
        'buttons:Show button assignments'
        'gesture:Set gesture button mode'
        'switch:Show Easy Switch channels'
        'flow:Show Logitech Flow status'
        'permissions:Check macOS permissions'
        'profiles:List all profiles'
        'init:Generate TOML config from device'
        'apply:Apply TOML config file'
        'daemon:Auto-apply config on connect'
        'export:Export config to JSON'
        'import:Import config from JSON'
        'reset:Reset device to defaults'
        'raw:Send raw request to agent'
    )

    local -a set_params
    set_params=(dpi speed smartshift smartshift-sensitivity scroll-speed scroll-direction thumb-speed thumb-direction thumb-smooth)

    local -a button_names
    button_names=(middle back forward gesture)

    local -a actions
    actions=(
        back forward middle mission-control launchpad smart-zoom
        undo redo copy paste cut screenshot emoji search
        desktop close-tab do-not-disturb lookup switch-apps
        dictation gesture mode-shift
    )

    local -a gesture_modes
    gesture_modes=(window media pan zoom app custom)

    _arguments -C \
        '--device[Device name or ID]:device:' \
        '-d[Device name or ID]:device:' \
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
                    _arguments '--profile[App profile]:profile:(safari chrome excel powerpoint word zoom)'
                    ;;
                gesture)
                    case $CURRENT in
                        2) _describe 'mode' gesture_modes ;;
                    esac
                    ;;
                buttons)
                    _arguments '--profile[App profile]:profile:(safari chrome excel powerpoint word zoom)'
                    ;;
                export|init)
                    _files -g '*.json' -g '*.toml'
                    ;;
                import)
                    _files -g '*.json'
                    ;;
                apply|daemon)
                    _files -g '*.toml'
                    ;;
                reset)
                    _arguments '-y[Skip confirmation]' '--yes[Skip confirmation]'
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
