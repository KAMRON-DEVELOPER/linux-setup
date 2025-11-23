return {
  {
    "preservim/tagbar",
    config = function()
      vim.keymap.set("n", "<Leader>tb", ":TagbarToggle<CR>", { desc = "Toggle Tagbar" })
    end,
  },
}
