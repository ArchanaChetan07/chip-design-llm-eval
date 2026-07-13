// testbenches/fsm/traffic_fsm_known_broken.sv
// Intentionally broken: yellow duration off by one AND a mutual-exclusion
// bug -- green output uses wrong comparison, causing a cycle where green
// and yellow are simultaneously asserted (a real safety-critical class of
// bug this benchmark category should catch).
module traffic_fsm #(
    parameter GREEN_CYCLES  = 4,
    parameter YELLOW_CYCLES = 2,
    parameter RED_CYCLES    = 3
) (
    input  logic clk, rst_n,
    output logic red, yellow, green
);
    typedef enum logic [1:0] {S_GREEN, S_YELLOW, S_RED} state_t;
    state_t state;
    integer counter;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= S_RED;
            counter <= 0;
        end else begin
            case (state)
                S_GREEN: begin
                    if (counter >= GREEN_CYCLES) begin  // BUG: off by one, runs one cycle long
                        state <= S_YELLOW; counter <= 0;
                    end else counter <= counter + 1;
                end
                S_YELLOW: begin
                    if (counter >= YELLOW_CYCLES - 1) begin
                        state <= S_RED; counter <= 0;
                    end else counter <= counter + 1;
                end
                S_RED: begin
                    if (counter >= RED_CYCLES - 1) begin
                        state <= S_GREEN; counter <= 0;
                    end else counter <= counter + 1;
                end
                default: state <= S_RED;
            endcase
        end
    end

    assign red    = (state == S_RED);
    assign yellow = (state == S_YELLOW);
    // BUG: green asserted one cycle too broadly (overlaps with yellow's
    // first cycle due to the off-by-one above)
    assign green  = (state == S_GREEN) || (state == S_YELLOW && counter == 0);
endmodule
