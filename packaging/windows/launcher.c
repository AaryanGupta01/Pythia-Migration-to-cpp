/* PYTHIA Studio.exe -- the Windows app entry point.
 *
 * Starts the bundled Python (pythonw.exe: no console window) running `python -m pythia_studio --app`, which
 * serves the UI on localhost and opens it in a chromeless Edge/Chrome window. The bundled MinGW-w64 compiler
 * is found through PYTHIA_TOOLCHAIN. If Python exits with an error during start-up, a message box points at
 * the log file instead of failing silently.
 */
#ifndef UNICODE
#define UNICODE
#endif
#ifndef _UNICODE
#define _UNICODE
#endif
#include <windows.h>
#include <stdio.h>
#include <wchar.h>

#define BIG 4096

static void parent_dir(wchar_t *p) {
    wchar_t *s = wcsrchr(p, L'\\');
    if (s) *s = 0;
}

int WINAPI wWinMain(HINSTANCE inst, HINSTANCE prev, PWSTR args, int show) {
    (void)inst; (void)prev; (void)show;
    static wchar_t dir[BIG], py[BIG], tool[BIG], cmd[BIG * 2], msg[BIG];
    GetModuleFileNameW(NULL, dir, BIG);
    parent_dir(dir);
    swprintf(py, BIG, L"%ls\\python\\pythonw.exe", dir);
    swprintf(tool, BIG, L"%ls\\mingw64", dir);
    if (GetFileAttributesW(py) == INVALID_FILE_ATTRIBUTES) {
        MessageBoxW(NULL, L"The bundled Python runtime is missing.\n\nPlease reinstall PYTHIA Studio.", L"PYTHIA Studio", MB_ICONERROR);
        return 1;
    }
    SetEnvironmentVariableW(L"PYTHIA_TOOLCHAIN", tool);
    SetEnvironmentVariableW(L"PYTHONNOUSERSITE", L"1");
    swprintf(cmd, BIG * 2, L"\"%ls\" -m pythia_studio --app --auto-port %ls", py, args ? args : L"");

    STARTUPINFOW si;
    PROCESS_INFORMATION pi;
    ZeroMemory(&si, sizeof si);
    si.cb = sizeof si;
    ZeroMemory(&pi, sizeof pi);
    if (!CreateProcessW(NULL, cmd, NULL, NULL, FALSE, 0, NULL, dir, &si, &pi)) {
        swprintf(msg, BIG, L"Could not start the bundled Python (error %lu).\n\n%ls", GetLastError(), py);
        MessageBoxW(NULL, msg, L"PYTHIA Studio", MB_ICONERROR);
        return 1;
    }
    /* A healthy start keeps running (the server lives as long as the window). An early non-zero exit is an error. */
    if (WaitForSingleObject(pi.hProcess, 8000) == WAIT_OBJECT_0) {
        DWORD code = 0;
        GetExitCodeProcess(pi.hProcess, &code);
        if (code != 0) {
            swprintf(msg, BIG,
                     L"PYTHIA Studio could not start (exit code %lu).\n\n"
                     L"Details are in the log file:\n%%USERPROFILE%%\\.pythia-studio\\logs\\studio.log",
                     code);
            MessageBoxW(NULL, msg, L"PYTHIA Studio", MB_ICONERROR);
        }
    }
    CloseHandle(pi.hThread);
    CloseHandle(pi.hProcess);
    return 0;
}
